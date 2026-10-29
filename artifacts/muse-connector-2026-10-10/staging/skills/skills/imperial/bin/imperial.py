#!/usr/bin/env python3
"""Imperial Trading API CLI — full-surface helper.

Public reads need no auth. Trading calls need IMPERIAL_JWT env (or --jwt);
the JWT is never printed, logged, or written to disk by this script.

Mutating commands (order/cancel/update/collateral/batch/deposit/margin-mode/
sync/register/revoke/partner-register) require --confirm.

Auth flow (user signs in their own wallet):
  1. imperial.py auth-message --wallet <pk>        # prints message to sign
  2. user signs imperial:mobile-connect:{wallet}:{nonce} with their keypair
  3. imperial.py connect --wallet <pk> --message '<msg>' --signature '<sig>'
     -> prints one-time code
  4. imperial.py exchange --code <code>            # -> prints jwt + expiresAt
  5. export IMPERIAL_JWT='<jwt>'                  # paste by hand; never commit
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse

BASE = os.environ.get("IMPERIAL_API_BASE", "https://api.imperial.space")

def req(method, path, body=None, jwt=None, params=None, headers=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if jwt:
        h["Authorization"] = "Bearer " + jwt
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {"http_error": e.code}

def out(status, payload):
    # never echo a jwt
    if isinstance(payload, dict) and "jwt" in payload:
        payload = {k: ("<redacted>" if k == "jwt" else v) for k, v in payload.items()}
    print(json.dumps({"http": status, "data": payload}, indent=2, default=str))

def need_jwt(a):
    jwt = a.jwt or os.environ.get("IMPERIAL_JWT")
    if not jwt:
        sys.exit("error: trading calls need IMPERIAL_JWT env or --jwt")
    return jwt

def need_confirm(a, what):
    if not a.confirm:
        sys.exit(f"refusing {what} without --confirm")

P = argparse.ArgumentParser(description="Imperial Trading API CLI")
P.add_argument("--jwt", default=None, help="JWT (or IMPERIAL_JWT env)")
P.add_argument("--confirm", action="store_true", help="required for mutating calls")
sub = P.add_subparsers(dest="cmd", required=True)

# ---- auth helpers ----
s = sub.add_parser("auth-message", help="print the message the wallet must sign")
s.add_argument("--wallet", required=True)
s.add_argument("--delegate", default=None)

s = sub.add_parser("connect", help="POST /mobile/connect -> one-time code")
s.add_argument("--wallet", required=True)
s.add_argument("--message", required=True)
s.add_argument("--signature", required=True)
s.add_argument("--delegate", default=None)

s = sub.add_parser("exchange", help="POST /mobile/exchange -> jwt (redacted in output)")
s.add_argument("--code", required=True)

s = sub.add_parser("revoke", help="POST /mobile/revoke")

# ---- public reads ----
sub.add_parser("status", help="GET /status")
s = sub.add_parser("mark-prices", help="GET /mark-prices")
s = sub.add_parser("funding-rates", help="GET /funding-rates")
s = sub.add_parser("route", help="GET /route")
s.add_argument("--asset", required=True); s.add_argument("--side", required=True)
s.add_argument("--notional", required=True); s.add_argument("--leverage", default=None)
s.add_argument("--hold-hours", default=None); s.add_argument("--wallet", default=None)
s.add_argument("--profile", default=None, dest="profileIndex")
s = sub.add_parser("priority-fee", help="GET /priority-fee")
s = sub.add_parser("close-slippage", help="GET /close-slippage")

for name, path in [("phoenix-markets", "/phoenix/markets"),
                   ("phoenix-mark-prices", "/phoenix/mark-prices"),
                   ("phoenix-depth", "/phoenix/depth"),
                   ("phoenix-volumes", "/phoenix/volumes"),
                   ("gmtrade-markets", "/gmtrade/markets"),
                   ("gmtrade-funding-rates", "/gmtrade/funding-rates"),
                   ("gmtrade-liquidity", "/gmtrade/liquidity"),
                   ("jupiter-pool-info", "/jupiter/pool-info")]:
    sub.add_parser(name, help="GET " + path)

s = sub.add_parser("positions", help="GET /positions")
s.add_argument("--wallet", required=True); s.add_argument("--underwriter", default=None)
s = sub.add_parser("orders", help="GET /orders")
s.add_argument("--wallet", required=True); s.add_argument("--underwriter", default=None)
s = sub.add_parser("order-history", help="GET /order-history")
s.add_argument("--wallet", required=True); s.add_argument("--limit", default=None)
s.add_argument("--status", default=None)
s = sub.add_parser("trades", help="GET /trades")
s.add_argument("--wallet", required=True); s.add_argument("--limit", default=None)
s = sub.add_parser("pnl-history", help="GET /pnl-history")
s.add_argument("--wallet", required=True); s.add_argument("--resolution", default="1d")
s = sub.add_parser("funding-history", help="GET /funding-history")
s.add_argument("--wallet", required=True); s.add_argument("--limit", default=None)
s = sub.add_parser("deposit-history", help="GET /deposit-history")
s.add_argument("--wallet", required=True); s.add_argument("--limit", default=None)
s = sub.add_parser("phoenix-direct-positions", help="GET /phoenix/direct-positions")
s.add_argument("--wallet", required=True)
s = sub.add_parser("phoenix-margin-account", help="GET /phoenix/margin-account")
s.add_argument("--wallet", required=True); s.add_argument("--profile", required=True, dest="profileIndex")
s = sub.add_parser("profiles", help="GET /passthrough/.../profiles")
s.add_argument("--wallet", required=True)
s = sub.add_parser("passthrough-orders", help="GET /passthrough/.../orders")
s.add_argument("--wallet", required=True); s.add_argument("--profile", default=None, dest="profile_index")

s = sub.add_parser("touch-markets", help="GET /touch/markets")
s = sub.add_parser("touch-deals", help="GET /touch/deals")
s.add_argument("--market-id", default=None, dest="marketId")
s = sub.add_parser("touch-positions", help="GET /touch/positions")
s.add_argument("--wallet", required=True)

s = sub.add_parser("armada-markets", help="GET /armada/markets")
s = sub.add_parser("armada-status", help="GET /armada/status")
s = sub.add_parser("armada-quote", help="GET /armada/quote")
s.add_argument("--asset", required=True); s.add_argument("--side", required=True)
s.add_argument("--notional", required=True, dest="notionalUsd")
s.add_argument("--wallet", required=True)
s = sub.add_parser("armada-orderbook", help="GET /armada/orderbook")
s.add_argument("--asset", required=True)
s = sub.add_parser("armada-open-availability", help="GET /armada/open-availability")
s.add_argument("--asset", required=True); s.add_argument("--side", required=True)
s.add_argument("--notional", required=True, dest="notionalUsd")

s = sub.add_parser("stats-summary", help="GET /stats/summary")
s = sub.add_parser("stats-markets", help="GET /stats/markets")
s = sub.add_parser("builder-summary", help="GET /mobile/builder/summary")
s.add_argument("--code", required=True)

# ---- JWT-gated reads ----
sub.add_parser("balances", help="GET /mobile/balances")
sub.add_parser("points", help="GET /mobile/points")
sub.add_parser("partner-registration", help="GET /mobile/partner/registration")

# ---- trading (mutating) ----
s = sub.add_parser("preflight", help="POST /mobile/orders/preflight")
s.add_argument("--body", required=True, help="order JSON file or '-' for stdin")
s = sub.add_parser("place-order", help="POST /mobile/orders")
s.add_argument("--body", required=True, help="order JSON file or '-' for stdin")
s = sub.add_parser("batch", help="POST /mobile/orders/batch")
s.add_argument("--body", required=True, help='{"entry": {...}, "closeOrders": [...]} JSON file or -')
s = sub.add_parser("cancel", help="POST /mobile/orders/cancel")
s.add_argument("--wallet", required=True); s.add_argument("--profile", required=True)
s.add_argument("--order-pda", required=True, dest="orderPda")
s.add_argument("--cascade", action="store_true")
s = sub.add_parser("update", help="POST /mobile/orders/update")
s.add_argument("--wallet", required=True); s.add_argument("--profile", required=True)
s.add_argument("--order-pda", required=True, dest="orderPda")
s.add_argument("--set", default=None, help="JSON of fields to change")
s = sub.add_parser("collateral", help="POST /mobile/orders/collateral")
s.add_argument("--body", required=True, help="collateral JSON file or '-' for stdin")
s = sub.add_parser("deposit", help="POST /deposit/build-tx")
s.add_argument("--wallet", required=True); s.add_argument("--profile", required=True)
s.add_argument("--mode", required=True, choices=["deposit", "withdraw"])
s.add_argument("--amount", required=True, help="USDC native units (6-decimal)")
s.add_argument("--defer", action="store_true")
s = sub.add_parser("margin-mode", help="PUT .../profiles/{i}/margin-mode")
s.add_argument("--wallet", required=True); s.add_argument("--profile", required=True)
s.add_argument("--mode", required=True, choices=["unified", "isolated"])
s = sub.add_parser("sync", help="POST .../profiles/{i}/sync (residue reclaim)")
s.add_argument("--wallet", required=True); s.add_argument("--profile", required=True)
s = sub.add_parser("phoenix-register", help="POST /phoenix/register")
s = sub.add_parser("partner-register", help="POST /mobile/partner/register")
s.add_argument("--code", required=True)

a = P.parse_args()

def load_body(spec):
    return json.load(sys.stdin if spec == "-" else open(spec))

PATHS = {
    "status": "/api/v1/status", "mark-prices": "/api/v1/mark-prices",
    "funding-rates": "/api/v1/funding-rates", "priority-fee": "/api/v1/priority-fee",
    "close-slippage": "/api/v1/close-slippage",
    "phoenix-markets": "/api/v1/phoenix/markets",
    "phoenix-mark-prices": "/api/v1/phoenix/mark-prices",
    "phoenix-depth": "/api/v1/phoenix/depth",
    "phoenix-volumes": "/api/v1/phoenix/volumes",
    "gmtrade-markets": "/api/v1/gmtrade/markets",
    "gmtrade-funding-rates": "/api/v1/gmtrade/funding-rates",
    "gmtrade-liquidity": "/api/v1/gmtrade/liquidity",
    "jupiter-pool-info": "/api/v1/jupiter/pool-info",
    "touch-markets": "/api/v1/touch/markets",
    "armada-markets": "/api/v1/armada/markets",
    "armada-status": "/api/v1/armada/status",
    "stats-summary": "/api/v1/stats/summary",
    "stats-markets": "/api/v1/stats/markets",
    "balances": "/api/v1/mobile/balances",
    "points": "/api/v1/mobile/points",
    "partner-registration": "/api/v1/mobile/partner/registration",
}

c = a.cmd
if c == "auth-message":
    nonce = int(time.time() * 1000)
    if a.delegate:
        print(f"imperial:delegate-connect:{a.wallet}:{a.delegate}:{nonce}")
    else:
        print(f"imperial:mobile-connect:{a.wallet}:{nonce}")
elif c == "connect":
    body = {"wallet": a.wallet, "message": a.message, "signature": a.signature,
            "delegate": a.delegate}
    out(*req("POST", "/api/v1/mobile/connect", body))
elif c == "exchange":
    out(*req("POST", "/api/v1/mobile/exchange", {"code": a.code}))
elif c == "revoke":
    need_confirm(a, "revoke"); out(*req("POST", "/api/v1/mobile/revoke", {}, need_jwt(a)))
elif c in PATHS:
    jwt = need_jwt(a) if c in ("balances", "points", "partner-registration") else None
    out(*req("GET", PATHS[c], jwt=jwt))
elif c == "route":
    out(*req("GET", "/api/v1/route", params={"asset": a.asset, "side": a.side,
        "notional": a.notional, "desiredLeverage": a.leverage,
        "holdHours": a.hold_hours if hasattr(a, "hold_hours") else None,
        "wallet": a.wallet, "profileIndex": a.profileIndex}))
elif c == "positions":
    out(*req("GET", "/api/v1/positions", params={"walletAddress": a.wallet, "underwriter": a.underwriter}))
elif c == "orders":
    out(*req("GET", "/api/v1/orders", params={"walletAddress": a.wallet, "underwriter": a.underwriter}))
elif c == "order-history":
    out(*req("GET", "/api/v1/order-history", params={"walletAddress": a.wallet, "limit": a.limit, "status": a.status}))
elif c == "trades":
    out(*req("GET", "/api/v1/trades", params={"walletAddress": a.wallet, "limit": a.limit}))
elif c == "pnl-history":
    out(*req("GET", "/api/v1/pnl-history", params={"walletAddress": a.wallet, "resolution": a.resolution}))
elif c == "funding-history":
    out(*req("GET", "/api/v1/funding-history", params={"walletAddress": a.wallet, "limit": a.limit}))
elif c == "deposit-history":
    out(*req("GET", "/api/v1/deposit-history", params={"walletAddress": a.wallet, "limit": a.limit}))
elif c == "phoenix-direct-positions":
    out(*req("GET", "/api/v1/phoenix/direct-positions", params={"walletAddress": a.wallet}))
elif c == "phoenix-margin-account":
    out(*req("GET", "/api/v1/phoenix/margin-account", params={"walletAddress": a.wallet, "profileIndex": a.profileIndex}))
elif c == "profiles":
    out(*req("GET", f"/api/v1/passthrough/users/{a.wallet}/profiles"))
elif c == "passthrough-orders":
    out(*req("GET", f"/api/v1/passthrough/users/{a.wallet}/orders", params={"profile_index": a.profile_index}))
elif c == "touch-deals":
    out(*req("GET", "/api/v1/touch/deals", params={"marketId": a.marketId}))
elif c == "touch-positions":
    out(*req("GET", "/api/v1/touch/positions", params={"walletAddress": a.wallet}))
elif c == "armada-quote":
    out(*req("GET", "/api/v1/armada/quote", params={"asset": a.asset, "side": a.side,
        "notionalUsd": a.notionalUsd, "wallet": a.wallet}))
elif c == "armada-orderbook":
    out(*req("GET", "/api/v1/armada/orderbook", params={"asset": a.asset}))
elif c == "armada-open-availability":
    out(*req("GET", "/api/v1/armada/open-availability", params={"asset": a.asset,
        "side": a.side, "notionalUsd": a.notionalUsd}))
elif c == "stats-markets":
    out(*req("GET", "/api/v1/stats/markets"))
elif c == "builder-summary":
    out(*req("GET", "/api/v1/mobile/builder/summary", params={"code": a.code}))
elif c == "preflight":
    out(*req("POST", "/api/v1/mobile/orders/preflight", load_body(a.body), need_jwt(a)))
elif c == "place-order":
    need_confirm(a, "place-order")
    st, pl = req("POST", "/api/v1/mobile/orders", load_body(a.body), need_jwt(a))
    if isinstance(pl, dict) and not pl.get("success"):
        print("ORDER REJECTED:", pl.get("errorCode"), "-", pl.get("error"), file=sys.stderr)
    out(st, pl)
elif c == "batch":
    need_confirm(a, "batch")
    out(*req("POST", "/api/v1/mobile/orders/batch", load_body(a.body), need_jwt(a)))
elif c == "cancel":
    need_confirm(a, "cancel")
    out(*req("POST", "/api/v1/mobile/orders/cancel",
        {"wallet": a.wallet, "profileIndex": int(a.profile), "orderPda": a.orderPda,
         "cascadeChildren": a.cascade}, need_jwt(a)))
elif c == "update":
    need_confirm(a, "update")
    body = {"wallet": a.wallet, "profileIndex": int(a.profile), "orderPda": a.orderPda}
    if a.set: body.update(json.loads(a.set))
    out(*req("POST", "/api/v1/mobile/orders/update", body, need_jwt(a)))
elif c == "collateral":
    need_confirm(a, "collateral")
    out(*req("POST", "/api/v1/mobile/orders/collateral", load_body(a.body), need_jwt(a)))
elif c == "deposit":
    need_confirm(a, "deposit build-tx")
    out(*req("POST", "/api/v1/deposit/build-tx",
        {"wallet": a.wallet, "profileIndex": int(a.profile), "mode": a.mode,
         "amount": int(a.amount), "deferOperatorSignature": a.defer}, need_jwt(a)))
elif c == "margin-mode":
    need_confirm(a, "margin-mode switch")
    out(*req("PUT", f"/api/v1/passthrough/users/{a.wallet}/profiles/{a.profile}/margin-mode",
        {"marginMode": a.mode}, need_jwt(a)))
elif c == "sync":
    need_confirm(a, "sync")
    out(*req("POST", f"/api/v1/passthrough/users/{a.wallet}/profiles/{a.profile}/sync", {}, need_jwt(a)))
elif c == "phoenix-register":
    need_confirm(a, "phoenix-register")
    out(*req("POST", "/api/v1/phoenix/register", {}, need_jwt(a)))
elif c == "partner-register":
    need_confirm(a, "partner-register")
    out(*req("POST", "/api/v1/mobile/partner/register", {"code": a.code}, need_jwt(a)))
else:
    sys.exit(f"unknown command {c}")
