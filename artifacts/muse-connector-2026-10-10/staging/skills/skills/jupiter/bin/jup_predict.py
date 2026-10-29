#!/usr/bin/env python3
"""Jupiter Prediction API CLI (Forecast / bisonfi + polymarket + kalshi).

Base: https://api.jup.ag/prediction/v1  (BETA - subject to breaking changes)
Auth: stored custom.jupiter credential via authd surrogate (x-api-key header).

Read-only commands need no wallet. Order/close/claim commands BUILD an
unsigned transaction only -- signing happens in the user's browser, per the
no-local-keypairs rule. Nothing here signs or submits to Solana.

Value conventions (official):
  - 1_000_000 micro units = $1.00 (prices, deposits, P&L)
  - 1_000_000 micro-contract units = 1 contract (use contractsMicro /
    contractsDecimal; legacy whole-contract `contracts` can't express
    fractions)
  - Orderbook price_cents arrays are rounded; prefer *_dollars arrays
    (["0.0100", size]) for sub-cent precision
  - Forecast (bisonfi) buys: USDC only, 5-250 USDC per order
  - General buys: JupUSD or USDC, minimum 5 USD
  - Forecast markets: market IDs like BISON--UP / BISON--DOWN; settlement is
    automatic (no claim). Closed rounds return bisonfi_market_not_tradable;
    no routable liquidity returns no_route.
  - execution.context (type create_order or bisonfi_swap) must be passed
    UNCHANGED to /execute with the signed tx.

Subcommands (read-only):
  trading-status | vault-info | forecast
  events [--provider] [--category] [--subcategory] [--filter] [--tags]
         [--sort-by] [--sort-direction] [--start] [--end] [--include-markets]
  events-search --query [--provider] [--limit 1-20]
  event <eventId> [--include-markets]
  suggested <ownerPubkey> [--provider]
  scores --event-ids ID1,ID2 | event-score <eventId>
  event-markets <eventId> [--start] [--end]
  event-market <eventId> <marketId>
  market <marketId>
  orderbook <marketId>
  positions <ownerPubkey> [--market-id] [--market-pubkey] [--is-yes] [--bisonfi] [--start] [--end]
  position <positionPubkey>
  orders <ownerPubkey> [--start] [--end]
  order <orderPubkey>
  order-status <orderPubkey>
  history <ownerPubkey> [--position-pubkey] [--id] [--start] [--end]
  profile <ownerPubkey>
  pnl-history <ownerPubkey> [--interval 24h|1w|1m] [--count]
  trades [--limit]
  leaderboards [--period all_time|weekly|monthly] [--metric pnl|volume|win_rate] [--limit 1-100]

Subcommands (build unsigned tx only -- browser signs, then `execute`):
  buy --market-id ID --amount USD --owner OWNER [--side yes|no] [--mint usdc|jupusd]
  execute --signed-tx BASE64 [--context JSON] [--request-id ID]
  sell --position POSITION_PUBKEY --owner OWNER        (close entire position)
  sell-all --owner OWNER [--slippage-bps 2500]         (close every position)
  claim --position POSITION_PUBKEY --owner OWNER        (claimable winners only)

Examples:
  jup_predict.py trading-status
  jup_predict.py events --provider bisonfi --category crypto --tags 15m --include-markets
  jup_predict.py market BISON--UP
  jup_predict.py orderbook BISON--UP
  jup_predict.py buy --market-id BISON--UP --amount 5 --owner <pubkey>
  jup_predict.py execute --signed-tx <base64> --context '<context json>'
"""
import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from decimal import Decimal, InvalidOperation

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://api.jup.ag/prediction/v1"
ALLOWED = ["api.jup.ag"]
CRED = "custom.jupiter"

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUPUSD_MINT = "JuprjznTrTSp2UFa3ZBUFgwdAmtZCq4MQCwysN55USD"
DEPOSIT_MINTS = {"usdc": USDC_MINT, "jupusd": JUPUSD_MINT}

ERR = "HTTP error"
B58_ALPHABET = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def valid_pubkey(s):
    return (isinstance(s, str) and len(s) >= 32 and len(s) <= 44
            and all(c in B58_ALPHABET for c in s))


def req(method, path, data=None):
    url = BASE + (path if path.startswith("/") else "/" + path)
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("User-Agent", "jupiter-predict/1.0")
    r.add_header("accept", "application/json")
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        add_surrogate_to_request(r, CRED, allowed_hosts=ALLOWED)
    except DynamicCredentialError as e:
        return {"ok": False, "error": "credential: " + str(e)}
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        return read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:800]
        except Exception:
            body = "<unreadable>"
        return {"ok": False, "error": f"{ERR} {e.code}", "body": body}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def q(params):
    return "?" + urllib.parse.urlencode({k: v for k, v in params.items()
                                         if v is not None})


def micro_units(dollars_str):
    """Strict decimal -> integer micro-unit conversion (no float)."""
    try:
        d = Decimal(str(dollars_str))
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a decimal number, got %r" % dollars_str)
    if d <= 0:
        raise ValueError("amount must be positive, got %r" % dollars_str)
    return str(int(d * 1_000_000))


def fmt_usd(micro):
    try:
        v = int(micro) / 1_000_000
        return ("$%s" % f"{v:,.4f}").rstrip("0").rstrip(".")
    except Exception:
        return str(micro)


def fmt_events(payload):
    """Compact, human-readable event/market summary."""
    if isinstance(payload, dict) and not payload.get("ok", True):
        return payload
    data = payload.get("data", []) if isinstance(payload, dict) else payload
    pagination = payload.get("pagination") if isinstance(payload, dict) else None
    out = []
    for e in data:
        md = e.get("metadata", {}) or {}
        ev = {
            "eventId": e.get("eventId"),
            "title": md.get("title") or e.get("title"),
            "category": e.get("category"),
            "isLive": e.get("isLive"),
            "isActive": e.get("isActive"),
            "tags": e.get("tags"),
            "volumeUsd": fmt_usd(e.get("volumeUsd", 0)),
            "markets": [],
        }
        for m in e.get("markets") or []:
            p = m.get("pricing") or {}
            ev["markets"].append({
                "marketId": m.get("marketId"),
                "provider": m.get("provider"),
                "status": m.get("status"),
                "result": m.get("result"),
                "tradable": m.get("tradable"),
                "lifecycle": m.get("lifecycleStatus"),
                "outcomeSide": m.get("outcomeSide"),
                "outcomeMint": m.get("outcomeMint"),
                "openTime": m.get("openTime"),
                "closeTime": m.get("closeTime"),
                "buyYesUsd": fmt_usd(p.get("buyYesPriceUsd"))
                    if p.get("buyYesPriceUsd") is not None else None,
                "buyNoUsd": fmt_usd(p.get("buyNoPriceUsd"))
                    if p.get("buyNoPriceUsd") is not None else None,
                "sellYesUsd": fmt_usd(p.get("sellYesPriceUsd"))
                    if p.get("sellYesPriceUsd") is not None else None,
                "sellNoUsd": fmt_usd(p.get("sellNoPriceUsd"))
                    if p.get("sellNoPriceUsd") is not None else None,
            })
        out.append(ev)
    return {"events": out, "count": len(out), "pagination": pagination}


NOTE_SIGN = ("NOT SIGNED. Sign the transaction in the user's browser, then run "
             "`execute --signed-tx <base64> --context '<execution_context_json>'.")


def print_build(label, r):
    """Uniform unsigned-tx-build output: tx + execution context + meta."""
    if isinstance(r, dict) and r.get("transaction"):
        ex = r.get("execution") or {}
        print(json.dumps({
            "unsigned_transaction_base64": r["transaction"],
            "execution_endpoint": ex.get("endpoint"),
            "execution_context": ex.get("context"),
            "required_signers": r.get("requiredSigners"),
            "order": r.get("order"),
            "txMeta": r.get("txMeta"),
            "note": "UNSIGNED. " + label,
        }, indent=1))
    else:
        print(json.dumps(r, indent=1))


def fail(msg):
    print(json.dumps({"ok": False, "error": msg}, indent=1))
    return 1


def main():
    ap = argparse.ArgumentParser(description="Jupiter Prediction API CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("trading-status")
    sub.add_parser("vault-info")

    p = sub.add_parser("forecast")
    p.add_argument("--market-id", required=True,
                   help="Market ID for the forecast time-series")

    p = sub.add_parser("events")
    p.add_argument("--provider", default="bisonfi",
                   choices=["bisonfi", "polymarket", "kalshi", "gx"])
    p.add_argument("--category",
                   choices=["all", "crypto", "sports", "politics", "esports",
                            "culture", "economics", "tech"])
    p.add_argument("--subcategory")
    p.add_argument("--filter", choices=["new", "live", "trending", "upcoming"])
    p.add_argument("--tags")
    p.add_argument("--sort-by", choices=["volume", "beginAt"])
    p.add_argument("--sort-direction", choices=["asc", "desc"])
    p.add_argument("--start", default="0")
    p.add_argument("--end", default="20")
    p.add_argument("--include-markets", action="store_true")
    p.add_argument("--include-all-markets", action="store_true")

    p = sub.add_parser("events-search")
    p.add_argument("--query", required=True)
    p.add_argument("--provider", default="polymarket",
                   choices=["bisonfi", "polymarket", "kalshi", "gx"])
    p.add_argument("--limit", default="10")

    p = sub.add_parser("event")
    p.add_argument("eventId")
    p.add_argument("--include-markets", action="store_true")
    p.add_argument("--include-all-markets", action="store_true")

    p = sub.add_parser("suggested")
    p.add_argument("ownerPubkey")
    p.add_argument("--provider", default="polymarket",
                   choices=["bisonfi", "polymarket", "kalshi", "gx"])

    p = sub.add_parser("scores")
    p.add_argument("--event-ids", required=True,
                   help="Comma-separated event IDs, max 100")
    p = sub.add_parser("event-score")
    p.add_argument("eventId")

    p = sub.add_parser("event-markets")
    p.add_argument("eventId")
    p.add_argument("--start", default="0")
    p.add_argument("--end", default="20")

    p = sub.add_parser("event-market")
    p.add_argument("eventId")
    p.add_argument("marketId")

    p = sub.add_parser("market")
    p.add_argument("marketId")
    p = sub.add_parser("orderbook")
    p.add_argument("marketId")

    p = sub.add_parser("positions")
    p.add_argument("ownerPubkey")
    p.add_argument("--market-id")
    p.add_argument("--market-pubkey")
    p.add_argument("--is-yes", choices=["true", "false"])
    p.add_argument("--bisonfi", action="store_true",
                   help="Client-side filter to bisonfi (Forecast) markets")
    p.add_argument("--start", default="0")
    p.add_argument("--end", default="20")

    p = sub.add_parser("position")
    p.add_argument("positionPubkey")

    p = sub.add_parser("orders")
    p.add_argument("ownerPubkey")
    p.add_argument("--start", default="0")
    p.add_argument("--end", default="20")

    p = sub.add_parser("order")
    p.add_argument("orderPubkey")
    p = sub.add_parser("order-status")
    p.add_argument("orderPubkey")

    p = sub.add_parser("history")
    p.add_argument("ownerPubkey")
    p.add_argument("--position-pubkey")
    p.add_argument("--id", help="Filter by history event ID")
    p.add_argument("--start", default="0")
    p.add_argument("--end", default="20")

    p = sub.add_parser("profile")
    p.add_argument("ownerPubkey")

    p = sub.add_parser("pnl-history")
    p.add_argument("ownerPubkey")
    p.add_argument("--interval", default="1w", choices=["24h", "1w", "1m"])
    p.add_argument("--count", default="10")

    p = sub.add_parser("trades")
    p.add_argument("--limit", default="20")

    p = sub.add_parser("leaderboards")
    p.add_argument("--period", default="all_time",
                   choices=["all_time", "weekly", "monthly"])
    p.add_argument("--metric", default="pnl",
                   choices=["pnl", "volume", "win_rate"])
    p.add_argument("--limit", default="20")

    # ---- transaction builders (unsigned only) ----
    p = sub.add_parser("buy")
    p.add_argument("--market-id", required=True)
    p.add_argument("--amount", help="Deposit amount in deposit-mint units, e.g. 5")
    p.add_argument("--usdc", help="Deprecated alias for --amount")
    p.add_argument("--owner", required=True)
    p.add_argument("--side", default="yes", choices=["yes", "no"])
    p.add_argument("--mint", default="usdc", choices=["usdc", "jupusd"],
                   help=("Deposit mint. Forecast (bisonfi): USDC only, 5-250. "
                         "General: USDC or JupUSD, min 5."))

    p = sub.add_parser("execute")
    p.add_argument("--signed-tx", required=True,
                   help="base64 signed tx from the browser")
    p.add_argument("--context", default=None,
                   help="execution.context JSON from the build (pass unchanged)")
    p.add_argument("--request-id", default=None)

    p = sub.add_parser("sell")
    p.add_argument("--position", required=True)
    p.add_argument("--owner", required=True)

    p = sub.add_parser("sell-all")
    p.add_argument("--owner", required=True)
    p.add_argument("--slippage-bps", default="2500",
                   help="Required slippage tolerance per sell, basis points")

    p = sub.add_parser("claim")
    p.add_argument("--position", required=True)
    p.add_argument("--owner", required=True)

    a = ap.parse_args()

    if a.cmd == "trading-status":
        print(json.dumps(req("GET", "/trading-status"), indent=1))
    elif a.cmd == "vault-info":
        print(json.dumps(req("GET", "/vault-info"), indent=1))
    elif a.cmd == "forecast":
        print(json.dumps(req("GET", "/forecast" + q({"marketId": a.market_id})),
                         indent=1))
    elif a.cmd == "events":
        path = "/events" + q({
            "provider": a.provider, "category": a.category,
            "subcategory": a.subcategory, "filter": a.filter,
            "tags": a.tags, "sortBy": a.sort_by,
            "sortDirection": a.sort_direction, "start": a.start, "end": a.end,
            "includeMarkets": "true" if a.include_markets else None,
            "includeAllMarkets": "true" if a.include_all_markets else None,
        })
        print(json.dumps(fmt_events(req("GET", path)), indent=1))
    elif a.cmd == "events-search":
        limit = max(1, min(20, int(a.limit)))
        path = ("/events/search" + q({"query": a.query, "limit": limit,
                                      "provider": a.provider}))
        print(json.dumps(fmt_events(req("GET", path)), indent=1))
    elif a.cmd == "event":
        path = (f"/events/{a.eventId}" + q({
            "includeMarkets": "true" if a.include_markets else None,
            "includeAllMarkets": "true" if a.include_all_markets else None,
        }))
        print(json.dumps(req("GET", path), indent=1))
    elif a.cmd == "suggested":
        if not valid_pubkey(a.ownerPubkey):
            return fail("invalid ownerPubkey")
        path = (f"/events/suggested/{a.ownerPubkey}"
                + q({"provider": a.provider}))
        print(json.dumps(req("GET", path), indent=1))
    elif a.cmd == "scores":
        print(json.dumps(req("GET", "/events/scores"
                             + q({"eventIds": a.event_ids})), indent=1))
    elif a.cmd == "event-score":
        print(json.dumps(req("GET", f"/events/{a.eventId}/score"), indent=1))
    elif a.cmd == "event-markets":
        path = (f"/events/{a.eventId}/markets"
                + q({"start": a.start, "end": a.end}))
        print(json.dumps(req("GET", path), indent=1))
    elif a.cmd == "event-market":
        print(json.dumps(req("GET", f"/events/{a.eventId}/markets/{a.marketId}"),
                         indent=1))
    elif a.cmd == "market":
        print(json.dumps(req("GET", f"/markets/{a.marketId}"), indent=1))
    elif a.cmd == "orderbook":
        r = req("GET", f"/orderbook/{a.marketId}")
        if isinstance(r, dict) and "yes_dollars" in r:
            # Prefer exact dollar-string levels (sub-cent safe)
            print(json.dumps({
                "yes": r.get("yes_dollars"), "no": r.get("no_dollars"),
                "note": ("Levels are [price_usd_string, size]; "
                         "size may be fractional."),
            }, indent=1))
        else:
            print(json.dumps(r, indent=1))
    elif a.cmd == "positions":
        if not valid_pubkey(a.ownerPubkey):
            return fail("invalid ownerPubkey")
        path = "/positions" + q({
            "ownerPubkey": a.ownerPubkey, "marketId": a.market_id,
            "marketPubkey": a.market_pubkey, "isYes": a.is_yes,
            "start": a.start, "end": a.end,
        })
        r = req("GET", path)
        if a.bisonfi and isinstance(r, dict) and isinstance(r.get("data"), list):
            r["data"] = [x for x in r["data"]
                         if str(x.get("marketId", "")).startswith("BISON-")]
            r["pagination"] = {"filtered_to_bisonfi": True}
        print(json.dumps(r, indent=1))
    elif a.cmd == "position":
        print(json.dumps(req("GET", f"/positions/{a.positionPubkey}"),
                         indent=1))
    elif a.cmd == "orders":
        if not valid_pubkey(a.ownerPubkey):
            return fail("invalid ownerPubkey")
        path = ("/orders" + q({"ownerPubkey": a.ownerPubkey,
                               "start": a.start, "end": a.end}))
        print(json.dumps(req("GET", path), indent=1))
    elif a.cmd == "order":
        print(json.dumps(req("GET", f"/orders/{a.orderPubkey}"), indent=1))
    elif a.cmd == "order-status":
        print(json.dumps(req("GET", f"/orders/status/{a.orderPubkey}"),
                         indent=1))
    elif a.cmd == "history":
        if not valid_pubkey(a.ownerPubkey):
            return fail("invalid ownerPubkey")
        path = "/history" + q({"ownerPubkey": a.ownerPubkey,
                               "positionPubkey": a.position_pubkey,
                               "id": a.id, "start": a.start, "end": a.end})
        print(json.dumps(req("GET", path), indent=1))
    elif a.cmd == "profile":
        if not valid_pubkey(a.ownerPubkey):
            return fail("invalid ownerPubkey")
        print(json.dumps(req("GET", f"/profiles/{a.ownerPubkey}"), indent=1))
    elif a.cmd == "pnl-history":
        if not valid_pubkey(a.ownerPubkey):
            return fail("invalid ownerPubkey")
        path = (f"/profiles/{a.ownerPubkey}/pnl-history"
                + q({"interval": a.interval, "count": a.count}))
        print(json.dumps(req("GET", path), indent=1))
    elif a.cmd == "trades":
        r = req("GET", "/trades")
        if isinstance(r, dict) and isinstance(r.get("data"), list):
            r = {"data": r["data"][:int(a.limit)]}
        print(json.dumps(r, indent=1))
    elif a.cmd == "leaderboards":
        path = "/leaderboards" + q({"period": a.period, "metric": a.metric,
                                    "limit": a.limit})
        print(json.dumps(req("GET", path), indent=1))
    elif a.cmd == "buy":
        amount = a.amount or a.usdc
        if not amount:
            return fail("provide --amount (e.g. 5)")
        if not valid_pubkey(a.owner):
            return fail("invalid owner pubkey")
        try:
            micro = micro_units(amount)
            amt_dec = Decimal(str(amount))
        except ValueError as e:
            return fail(str(e))
        if amt_dec < 5:
            return fail(f"minimum order is 5 USD (got {amount})")
        if a.mint == "usdc" and amt_dec > 250:
            return fail("Forecast path enforces 5-250 USDC; larger sizes can "
                        "use the direct Swap path against the market's "
                        "outcomeMint")
        r = req("POST", "/orders", {
            "ownerPubkey": a.owner, "marketId": a.market_id,
            "isYes": a.side == "yes", "isBuy": True,
            "depositAmount": micro,
            "depositMint": DEPOSIT_MINTS[a.mint],
        })
        print_build(("Forecast builds settle atomically (atomic_swap). "
                     + NOTE_SIGN), r)
    elif a.cmd == "execute":
        body = {"signedTransaction": a.signed_tx}
        if a.context:
            try:
                body["context"] = json.loads(a.context)
            except json.JSONDecodeError as e:
                return fail(f"bad --context JSON: {e}")
        if a.request_id:
            body["requestId"] = a.request_id
        r = req("POST", "/execute", body)
        print(json.dumps(r, indent=1))
    elif a.cmd == "sell":
        if not valid_pubkey(a.owner):
            return fail("invalid owner pubkey")
        r = req("DELETE", f"/positions/{a.position}",
                {"ownerPubkey": a.owner})
        print_build("Sell build (closes entire position). " + NOTE_SIGN, r)
    elif a.cmd == "sell-all":
        if not valid_pubkey(a.owner):
            return fail("invalid owner pubkey")
        try:
            bps = int(a.slippage_bps)
        except ValueError:
            return fail("slippage-bps must be an integer")
        r = req("DELETE", "/positions", {
            "ownerPubkey": a.owner,
            "minSellPriceSlippageBps": bps,
        })
        if isinstance(r, dict) and isinstance(r.get("data"), list):
            builds = []
            for b in r["data"]:
                ex = b.get("execution") or {}
                builds.append({
                    "unsigned_transaction_base64": b.get("transaction"),
                    "execution_context": ex.get("context"),
                    "required_signers": b.get("requiredSigners"),
                    "txMeta": b.get("txMeta"),
                })
            print(json.dumps({
                "builds": builds, "count": len(builds),
                "note": ("UNSIGNED. Each entry needs its own browser "
                         "signature + /execute call with its own context. "
                         + NOTE_SIGN),
            }, indent=1))
        else:
            print(json.dumps(r, indent=1))
    elif a.cmd == "claim":
        if not valid_pubkey(a.owner):
            return fail("invalid owner pubkey")
        r = req("POST", f"/positions/{a.position}/claim",
                {"ownerPubkey": a.owner})
        print_build(("Winners may also auto-claim ~24h after settlement; "
                     "Forecast auto-settles and needs no claim. "
                     + NOTE_SIGN), r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
