#!/usr/bin/env python3
"""raydium.py — Raydium spot swaps via the public Trade API.

Browser-signing only. This CLI never holds a private key.

Commands:
  quote  --input-mint M --output-mint M --amount N [--slippage-bps 50]
         Read-only price quote. No wallet needed.
  build  --input-mint M --output-mint M --amount N --wallet PUBKEY
         [--slippage-bps 50] [--priority-fee 50000]
         Returns an UNSIGNED base64 VersionedTransaction for the user's
         browser wallet to sign, plus the quote details to show for approval.

Flow:
  1. raydium.py build ... -> unsigned_tx (base64)
  2. User signs unsigned_tx in their own browser wallet (fresh approval
     of exact terms: input, output, amount, slippage).
  3. User's wallet broadcasts, or the agent broadcasts the returned
     signed tx via RPC with `raydium.py broadcast --signed-tx <base64>`.

Never sign on behalf of the user. Never invent amounts.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request

TRADE_API = "https://transaction-v1.raydium.io"
API_V3 = "https://api-v3.raydium.io"
WSOL = "So11111111111111111111111111111111111111112"


def _get(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": "muse-raydium-skill/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _post(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                          "User-Agent": "muse-raydium-skill/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def cmd_quote(args: argparse.Namespace) -> int:
    data = _get(f"{TRADE_API}/compute/swap-base-in", {
        "inputMint": args.input_mint,
        "outputMint": args.output_mint,
        "amount": args.amount,
        "slippageBps": args.slippage_bps,
        "txVersion": "V0",
    })
    if not data.get("success"):
        print(json.dumps({"ok": False, "error": data.get("msg", "quote failed")}))
        return 1
    d = data["data"]
    print(json.dumps({
        "ok": True,
        "input_mint": d["inputMint"],
        "input_amount": d["inputAmount"],
        "output_mint": d["outputMint"],
        "output_amount": d["outputAmount"],
        "min_received": d["otherAmountThreshold"],
        "slippage_bps": d["slippageBps"],
        "price_impact_pct": d.get("priceImpactPct"),
        "route_plan": [{"pool": r.get("poolId"), "in": r.get("inputMint"), "out": r.get("outputMint")}
                       for r in d.get("routePlan", [])],
    }, indent=2))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    data = _get(f"{TRADE_API}/transaction/swap-base-in", {
        "inputMint": args.input_mint,
        "outputMint": args.output_mint,
        "amount": args.amount,
        "slippageBps": args.slippage_bps,
        "wallet": args.wallet,
        "txVersion": "V0",
        "computeUnitPriceMicroLamports": args.priority_fee,
    })
    if not data.get("success"):
        print(json.dumps({"ok": False, "error": data.get("msg", "tx build failed")}))
        return 1
    d = data["data"]
    swap = d.get("swapResponse", {})
    print(json.dumps({
        "ok": True,
        "unsigned_tx": d["tx"]["transaction"],
        "input_mint": swap.get("inputMint", args.input_mint),
        "input_amount": swap.get("inputAmount", args.amount),
        "output_mint": swap.get("outputMint", args.output_mint),
        "output_amount": swap.get("outputAmount"),
        "min_received": swap.get("otherAmountThreshold"),
        "slippage_bps": args.slippage_bps,
        "note": "UNSIGNED. Have the user sign this exact transaction in their browser wallet.",
    }, indent=2))
    return 0


def cmd_price(args: argparse.Namespace) -> int:
    mints = ",".join(args.mints)
    data = _get(f"{API_V3}/mint/price", {"mints": mints})
    if not data.get("success"):
        print(json.dumps({"ok": False, "error": data.get("msg", "price lookup failed")}))
        return 1
    print(json.dumps({"ok": True, "prices": data["data"]}, indent=2))
    return 0


def cmd_broadcast(args: argparse.Namespace) -> int:
    """Broadcast a user-signed transaction. RPC URL required."""
    try:
        from solders.transaction import VersionedTransaction  # noqa
    except ImportError:
        print(json.dumps({"ok": False,
                          "error": "solders not installed; broadcast from the user's wallet instead"}))
        return 1
    raw = base64.b64decode(args.signed_tx)
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
        "params": [base64.b64encode(raw).decode(),
                   {"encoding": "base64", "skipPreflight": False,
                    "maxRetries": 3}],
    }
    try:
        res = _post(args.rpc, payload)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"rpc error: {e}"}))
        return 1
    if "error" in res:
        print(json.dumps({"ok": False, "error": res["error"]}))
        return 1
    print(json.dumps({"ok": True, "signature": res["result"]}))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Raydium swaps (browser-signing only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quote", help="read-only swap quote")
    q.add_argument("--input-mint", required=True)
    q.add_argument("--output-mint", required=True)
    q.add_argument("--amount", required=True, help="input amount in base units (lamports / token decimals)")
    q.add_argument("--slippage-bps", type=int, default=50)
    q.set_defaults(fn=cmd_quote)

    b = sub.add_parser("build", help="build UNSIGNED swap tx for browser signing")
    b.add_argument("--input-mint", required=True)
    b.add_argument("--output-mint", required=True)
    b.add_argument("--amount", required=True)
    b.add_argument("--wallet", required=True, help="user's wallet pubkey (fee payer / signer)")
    b.add_argument("--slippage-bps", type=int, default=50)
    b.add_argument("--priority-fee", type=int, default=50000,
                   help="compute unit price in micro-lamports")
    b.set_defaults(fn=cmd_build)

    pr = sub.add_parser("price", help="USD prices for mints")
    pr.add_argument("--mints", nargs="+", required=True)
    pr.set_defaults(fn=cmd_price)

    br = sub.add_parser("broadcast", help="broadcast a user-signed tx")
    br.add_argument("--signed-tx", required=True, help="base64 signed transaction from the user's wallet")
    br.add_argument("--rpc", default="https://api.mainnet-beta.solana.com")
    br.set_defaults(fn=cmd_broadcast)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
