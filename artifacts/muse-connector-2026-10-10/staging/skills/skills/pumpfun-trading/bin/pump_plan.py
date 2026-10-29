#!/usr/bin/env python3
"""pump_plan.py — DRY-RUN pump.fun trade / creator-fee-claim plan builder.

Builds a plan JSON and prints the exact chat-approval summary the operator
pastes to the user. Signs NOTHING, broadcasts NOTHING, fetches NOTHING from
the network (offline v1 — quote enrichment via Helius/RPC is a follow-up).

Usage:
  pump_plan.py --mint <MINT> --side buy --amount-sol 0.05 [--slippage 0.03]
  pump_plan.py --mint <MINT> --side sell --amount-tokens 1000000 [--slippage 0.03]
  pump_plan.py --mint <MINT> --side claim-fees --creator <CREATOR_WALLET>

Plan files: ~/workspace/skills/pumpfun-trading/state/plans/<mint>-<ts>.plan.json
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS_DIR = os.path.join(BASE, "state", "plans")


def b58decode(s):
    n = 0
    for ch in s:
        if ch not in B58_ALPHABET:
            raise ValueError(f"invalid base58 character: {ch!r}")
        n = n * 58 + B58_ALPHABET.index(ch)
    pad = len(s) - len(s.lstrip("1"))
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad + body


def valid_pubkey(s, label):
    try:
        raw = b58decode(s)
    except ValueError as e:
        raise SystemExit(f"Invalid {label}: {e}")
    if len(raw) != 32:
        raise SystemExit(f"Invalid {label}: decodes to {len(raw)} bytes, expected 32")
    return s


def main():
    p = argparse.ArgumentParser(
        description="Build a DRY-RUN pump.fun trade/claim plan. Offline v1: "
                    "no network, no signatures, no broadcast.")
    p.add_argument("--mint", required=True, help="Token mint (base58, 32 bytes)")
    p.add_argument("--side", required=True, choices=["buy", "sell", "claim-fees"])
    p.add_argument("--amount-sol", type=float, default=None,
                   help="SOL to spend (buy only)")
    p.add_argument("--amount-tokens", default=None,
                   help="Tokens to sell (sell only, raw token units, integer preferred)")
    p.add_argument("--slippage", type=float, default=0.03,
                   help="Slippage as decimal, e.g. 0.03 = 3%% (default 0.03)")
    p.add_argument("--creator", default=None,
                   help="Creator wallet (REQUIRED for claim-fees)")
    a = p.parse_args()

    mint = valid_pubkey(a.mint, "mint")

    if not (0 < a.slippage <= 0.5):
        raise SystemExit("Invalid --slippage: must be > 0 and <= 0.5 (e.g. 0.03 = 3%)")
    slippage_bps = int(round(a.slippage * 10000))

    amount = None
    max_cost_sol = None
    creator = None

    if a.side == "buy":
        if a.amount_sol is None or a.amount_sol <= 0:
            raise SystemExit("--side buy requires --amount-sol > 0")
        if a.amount_tokens is not None:
            raise SystemExit("--amount-tokens is not used for buys")
        if a.creator is not None:
            creator = valid_pubkey(a.creator, "creator")
        amount = a.amount_sol
        max_cost_sol = round(a.amount_sol * (1 + a.slippage), 9)
    elif a.side == "sell":
        if a.amount_tokens is None:
            raise SystemExit("--side sell requires --amount-tokens > 0")
        try:
            amount_tokens = int(a.amount_tokens)
        except (TypeError, ValueError):
            try:
                amount_tokens = float(a.amount_tokens)
            except (TypeError, ValueError):
                raise SystemExit("--amount-tokens must be a number")
        if amount_tokens <= 0:
            raise SystemExit("--side sell requires --amount-tokens > 0")
        if a.amount_sol is not None:
            raise SystemExit("--amount-sol is not used for sells")
        if a.creator is not None:
            creator = valid_pubkey(a.creator, "creator")
        amount = amount_tokens
        max_cost_sol = None  # proceeds floor unknown offline; quote enrichment is a follow-up
    else:  # claim-fees
        if a.creator is None:
            raise SystemExit("--side claim-fees requires --creator <CREATOR_WALLET>")
        if a.amount_sol is not None or a.amount_tokens is not None:
            raise SystemExit("claim-fees takes no amount flags")
        creator = valid_pubkey(a.creator, "creator")
        amount = None
        max_cost_sol = None

    ts = int(time.time())
    plan = {
        "mint": mint,
        "side": a.side,
        "amount": amount,
        "slippage_bps": slippage_bps,
        "max_cost_sol": max_cost_sol,
        "creator": creator,
        "policy": {
            "needs_chat_approval": True,
            "browser_sign_only": True,
        },
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    os.makedirs(PLANS_DIR, exist_ok=True)
    path = os.path.join(PLANS_DIR, f"{mint}-{ts}.plan.json")
    with open(path, "w") as f:
        json.dump(plan, f, indent=2)

    slip_pct = f"{a.slippage * 100:.2f}%"
    if a.side == "buy":
        terms = (f"Spend: {amount} SOL, slippage {slip_pct} ({slippage_bps} bps), "
                 f"max cost {max_cost_sol} SOL")
    elif a.side == "sell":
        terms = (f"Sell: {amount} tokens, slippage {slip_pct} ({slippage_bps} bps). "
                 f"Expected SOL proceeds unknown offline — quote enrichment pending.")
    else:
        terms = (f"Claim creator fees to: {creator}\n"
                 f"Valid ONLY if the browser signing wallet IS the token creator. "
                 f"Operator: confirm in chat the user created this token; "
                 f"if not, REFUSE the claim and explain why.")

    summary = f"""============================================================
DRY-RUN PLAN — pump.fun {a.side.upper()} (nothing signed, nothing broadcast)
============================================================
Mint:      {mint}
Side:      {a.side}
{terms}
Plan file: {path}
Policy:    chat approval of EXACT terms required; browser-wallet signing only;
           no local keypairs for pump.fun trading.

--- paste to user for approval ---
🦞 Approval needed — pump.fun {a.side} (dry-run plan, nothing executed)
Mint: {mint}
{terms}
Step 1: you approve these exact terms in chat.
Step 2: you sign in your own browser wallet.
No signatures made yet. Reply "approve" to proceed.
--- end ---"""
    print(summary)


if __name__ == "__main__":
    main()
