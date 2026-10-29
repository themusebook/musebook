#!/usr/bin/env python3
"""Phoenix market-data CLI (read-only, paper-safe).

Wraps the Vulcan CLI for Phoenix perpetuals on Solana. Only read-only
subcommands are allowed: no wallet creation, no live orders, no
collateral movement, ever.

Usage:
  phx.py market list
  phx.py market ticker SOL
  phx.py market orderbook SOL --depth 5
  phx.py market candles SOL --interval 1h --limit 20
  phx.py market trades SOL --limit 20
  phx.py market funding-rates SOL --limit 20
  phx.py market info SOL
  phx.py ta report SOL --timeframe 1h
  phx.py history trades --symbol SOL --limit 20
  phx.py history funding --symbol SOL --limit 20
  phx.py history pnl --resolution daily --limit 30
  phx.py paper status
  phx.py paper buy SOL --notional-usdc 100 --type market
  phx.py paper positions

All output is JSON from vulcan, passed through unchanged.
"""
import json
import os
import shutil
import subprocess
import sys

VULCAN = os.environ.get("VULCAN_BIN") or shutil.which("vulcan") or os.path.expanduser("~/.local/bin/vulcan")

# Read-only / paper-safe commands. Anything else is refused.
ALLOWED = {
    "market": {"list", "info", "ticker", "orderbook", "candles", "trades", "funding-rates"},
    "ta": {"compute", "signal", "report"},
    "history": {"trades", "orders", "collateral", "funding", "pnl"},
    "paper": {"init", "reset", "status", "positions", "orders", "fills",
              "buy", "sell", "cancel", "cancel-all", "reconcile"},
    "portfolio": set(),  # `vulcan portfolio` takes no subcommand
}


def usage() -> int:
    print(__doc__.strip())
    return 2


def main() -> int:
    if len(sys.argv) < 2:
        return usage()
    group = sys.argv[1]
    if group not in ALLOWED:
        print(json.dumps({"ok": False, "error": f"refused: command group '{group}' is not read-only"}))
        return 1

    rest = sys.argv[2:]
    allowed_subs = ALLOWED[group]
    if allowed_subs:
        if not rest:
            return usage()
        sub = rest[0]
        if sub not in allowed_subs:
            print(json.dumps({"ok": False, "error": f"refused: vulcan {group} {sub} is not read-only"}))
            return 1
    else:
        if rest:
            print(json.dumps({"ok": False, "error": f"refused: vulcan {group} takes no subcommand"}))
            return 1

    cmd = [VULCAN, group] + rest + ["-o", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": f"vulcan binary not found at {VULCAN}"}))
        return 1
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "error": "vulcan timed out"}))
        return 1
    out = (proc.stdout or "").strip()
    if not out:
        print(json.dumps({"ok": False, "error": f"vulcan exited {proc.returncode}", "stderr": (proc.stderr or "").strip()[:500]}))
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
