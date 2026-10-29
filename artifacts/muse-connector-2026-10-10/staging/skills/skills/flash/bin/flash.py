#!/usr/bin/env python3
"""Call the Definitive Flash API with the stored custom.flash credential.

The API key is attached as the x-definitive-api-key header via authd surrogate;
this script never sees the raw key. Requests are restricted to
flash.definitive.fi.

Usage:
    flash.py quote --target-asset <mint> --contra-asset <mint> --side sell \\
        --qty 1.5 --order-type limit --limit-cross-price 100 --funder <wallet>
    flash.py order-status --order-id <id>
    flash.py list-orders --funder <wallet>
    flash.py cancel --order-id <id> --funder <wallet>   # prints cancel message to sign
    flash.py balances --wallet <wallet> --chain solana
    flash.py search --query weth --chain solana
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    add_surrogate_to_request,
    read_json_response,
)

BASE = "https://flash.definitive.fi/v1"
ALLOWED = ["flash.definitive.fi"]
CREDENTIAL = "custom.flash"


def call(method: str, path: str, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method=method
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}\n"
                 "Store a Flash API key first: ask the agent to set up custom.flash.")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            out = read_json_response(resp)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")
    except Exception as exc:  # urllib.error.HTTPError etc.
        body_text = ""
        try:
            body_text = exc.read().decode()[:2000]  # type: ignore[union-attr]
        except Exception:
            pass
        sys.exit(f"request failed: {exc}\n{body_text}")
    print(json.dumps(out, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quote", help="Request a quote (read-only)")
    q.add_argument("--target-asset", required=True)
    q.add_argument("--contra-asset", required=True)
    q.add_argument("--target-chain", default="solana")
    q.add_argument("--contra-chain", default="solana")
    q.add_argument("--side", choices=["buy", "sell"], required=True)
    q.add_argument("--qty", required=True, help="Decimal string in spent-asset units")
    q.add_argument("--order-type", default="market",
                   choices=["market", "limit", "twap", "stop", "stop-loss", "take-profit"])
    q.add_argument("--funder", required=True)
    q.add_argument("--limit-cross-price", default=None)
    q.add_argument("--limit-notional-price", default=None)
    q.add_argument("--max-slippage", default=None)
    q.add_argument("--max-price-impact", default=None)
    q.add_argument("--fee-bps", default=None, help="flashIntegratorFeeBps, e.g. 50")
    q.add_argument("--expire-time", default=None)
    q.add_argument("--force-minimal-allowance", action="store_true")

    o = sub.add_parser("order", help="Submit a signed order")
    o.add_argument("--order-json", required=True,
                   help="Full order JSON body (from quote + signatures)")

    s = sub.add_parser("order-status", help="Get order detail + fills")
    s.add_argument("--order-id", required=True)

    lo = sub.add_parser("list-orders", help="List orders for a funder")
    lo.add_argument("--funder", required=True)
    lo.add_argument("--page-size", default="25")

    c = sub.add_parser("cancel", help="Build a cancel request (needs signed cancel message)")
    c.add_argument("--order-id", required=True)
    c.add_argument("--cancel-message", required=True,
                   help="Funder-signed cancel message (base58)")
    c.add_argument("--funder", required=True)

    b = sub.add_parser("balances", help="Wallet token balances")
    b.add_argument("--wallet", required=True)
    b.add_argument("--chain", default="solana")

    se = sub.add_parser("search", help="Search tradable assets")
    se.add_argument("--query", required=True)
    se.add_argument("--chain", default=None)

    args = ap.parse_args()

    if args.cmd == "quote":
        body = {
            "targetChain": args.target_chain,
            "contraChain": args.contra_chain,
            "targetAsset": args.target_asset,
            "contraAsset": args.contra_asset,
            "side": args.side,
            "qty": args.qty,
            "orderType": args.order_type,
            "funderAddress": args.funder,
        }
        if args.limit_cross_price:
            body["limitCrossPrice"] = args.limit_cross_price
        if args.limit_notional_price:
            body["limitNotionalPrice"] = args.limit_notional_price
        if args.max_slippage:
            body["maxSlippage"] = args.max_slippage
        if args.max_price_impact:
            body["maxPriceImpact"] = args.max_price_impact
        if args.fee_bps:
            body["flashIntegratorFeeBps"] = args.fee_bps
        if args.expire_time:
            body["expireTime"] = args.expire_time
        if args.force_minimal_allowance:
            body["forceMinimalAllowance"] = True
        call("POST", "/quote", body)
    elif args.cmd == "order":
        try:
            body = json.loads(args.order_json)
        except json.JSONDecodeError:
            sys.exit("error: --order-json must be valid JSON")
        call("POST", "/order", body)
    elif args.cmd == "order-status":
        call("GET", f"/orders/{args.order_id}")
    elif args.cmd == "list-orders":
        call("GET", f"/orders?funderAddress={args.funder}&pageSize={args.page_size}")
    elif args.cmd == "cancel":
        call("POST", f"/orders/{args.order_id}/cancel", {
            "funderAddress": args.funder,
            "cancelMessage": args.cancel_message,
        })
    elif args.cmd == "balances":
        call("GET", f"/balances?wallet={args.wallet}&chain={args.chain}")
    elif args.cmd == "search":
        path = f"/search?query={args.query}"
        if args.chain:
            path += f"&chain={args.chain}"
        call("GET", path)


if __name__ == "__main__":
    main()
