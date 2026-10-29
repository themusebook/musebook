#!/usr/bin/env python3
"""Solana wallet balance snapshot with USD values.

Reads SOL + SPL token balances for the wallets listed in wallets.json,
prices them via Jupiter Price API v3, and prints a chat-friendly summary.
Stateless: prints current state only. Read-only: never signs or transfers.

Config — wallets.json (next to this script, or $WALLET_WATCH_CONFIG):
    {
      "wallets": { "my-trader": "<solana address>", "...": "..." },
      "symbols": { "<mint>": "LABEL", "...": "..." }
    }

Portable: resolves the helius skill bin from $SKILLS_DIR or ~/.muse/skills.

Run: python3 balances.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.expanduser("~/.muse/skills"))
CONFIG = os.environ.get(
    "WALLET_WATCH_CONFIG",
    os.path.join(HERE, "wallets.json"),
)
if not os.path.exists(CONFIG):
    alt = os.path.expanduser("~/.config/clawd/wallets.json")
    if os.path.exists(alt):
        CONFIG = alt

HELIUS = [sys.executable, os.path.join(SKILLS_DIR, "helius", "bin", "helius_rpc.py"),
          "--network", "mainnet"]

SOL_MINT = "So11111111111111111111111111111111111111112"
TOKEN_PROGRAMS = [
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",   # SPL Token
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",   # Token-2022
]


def load_config():
    if not os.path.exists(CONFIG):
        sys.exit(
            f"error: wallet config not found: {CONFIG}\n"
            "Create it, e.g.:\n"
            '  { "wallets": { "my-trader": "<solana address>" },\n'
            '    "symbols": { "<mint>": "LABEL" } }'
        )
    try:
        cfg = json.load(open(CONFIG))
        wallets = cfg["wallets"]
        assert isinstance(wallets, dict) and wallets
    except (json.JSONDecodeError, KeyError, AssertionError) as e:
        sys.exit(f"error: {CONFIG} needs a non-empty \"wallets\" object: {e}")
    return wallets, cfg.get("symbols", {})


def rpc(method, params):
    p = subprocess.run(HELIUS + ["--method", method, "--params", json.dumps(params)],
                       capture_output=True, text=True, timeout=60)
    p.check_returncode()
    return json.loads(p.stdout)["result"]["value"]


def short(addr):
    return addr[:6] + ".." + addr[-4:]


def fmt_usd(x):
    return "n/a" if x is None else f"${x:,.2f}"


def main():
    wallets, known_symbols = load_config()
    balances = {}   # name -> {"sol": float, "tokens": [(mint, ui_amount)]}
    mints = {SOL_MINT}
    for name, addr in wallets.items():
        lamports = rpc("getBalance", [addr])
        tokens = []
        for prog in TOKEN_PROGRAMS:
            try:
                accts = rpc("getTokenAccountsByOwner",
                            [addr, {"programId": prog}, {"encoding": "jsonParsed"}])
            except Exception:
                continue
            for a in accts:
                info = a["account"]["data"]["parsed"]["info"]
                amt = info["tokenAmount"]
                ui = float(amt["uiAmountString"])
                if ui > 0:
                    tokens.append((info["mint"], ui))
                    mints.add(info["mint"])
        balances[name] = {"sol": lamports / 1e9, "tokens": tokens, "addr": addr}

    # Prices (single batched call, with retries)
    prices = {}
    url = "https://lite-api.jup.ag/price/v3?ids=" + ",".join(sorted(mints))
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "wallet-watch/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            for m, d in data.items():
                if isinstance(d, dict) and d.get("usdPrice"):
                    prices[m] = float(d["usdPrice"])
            last_err = None
            break
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    if last_err is not None:
        print(f"(price lookup failed: {last_err})", file=sys.stderr)

    sol_price = prices.get(SOL_MINT)
    now = datetime.now().astimezone().strftime("%a %Y-%m-%d %H:%M %Z")
    lines = ["\U0001f99e Wallet balances \u2014 " + now]
    if sol_price:
        lines.append(f"SOL {fmt_usd(sol_price)}")
    lines.append("")

    grand = 0.0
    grand_known = True
    for name, b in balances.items():
        sub = b["sol"] * sol_price if sol_price else None
        tlines = []
        for mint, ui in b["tokens"]:
            px = prices.get(mint)
            sym = known_symbols.get(mint, short(mint))
            val = ui * px if px else None
            tlines.append(f"  {sym}: {ui:,.2f} ({fmt_usd(val)})")
            if sub is not None and val is not None:
                sub += val
            else:
                sub = None
        if sub is not None:
            grand += sub
        else:
            grand_known = False
        sol_usd = b["sol"] * sol_price if sol_price else None
        lines.append(f"{name} ({short(b['addr'])})")
        lines.append(f"  SOL: {b['sol']:.6f} ({fmt_usd(sol_usd)})")
        lines.extend(tlines)
        lines.append(f"  subtotal: {fmt_usd(sub)}")
        lines.append("")

    lines.append(f"TOTAL: {fmt_usd(grand if grand_known else None)}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
