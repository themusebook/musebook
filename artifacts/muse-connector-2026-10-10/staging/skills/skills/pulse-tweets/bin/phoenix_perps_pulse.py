#!/usr/bin/env python3
"""Phoenix perps snapshot tweet pulse.

Posts one data-only tweet per run: mark prices, 24h change, open interest,
and funding for BTC / SOL / ETH perps on Phoenix. Read-only market data —
never touches wallets or trading.

Portable: resolves sibling skill bins from $SKILLS_DIR or ~/.muse/skills.
Set $PULSE_FOOTER for your own tagline (default: no footer).

Run once per schedule fire, e.g. hourly:
    python3 phoenix_perps_pulse.py [--dry-run]
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.expanduser("~/.muse/skills"))
LOG = os.path.join(HERE, "phoenix_perps_runs.log")
PHX = os.path.join(SKILLS_DIR, "phoenix", "bin", "phx.py")
POST = os.path.join(SKILLS_DIR, "x-connect", "bin", "post.py")
SYMS = ("BTC", "SOL", "ETH")
FOOTER = os.environ.get("PULSE_FOOTER", "").strip()


def run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        if err:
            out = (out + "\nSTDERR: " + err).strip()
        return p.returncode, out
    except Exception as e:
        return 1, f"ERR {e}"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"{ts} {msg}\n")


def fmt_usd(x):
    return f"${x:,.0f}" if x >= 1000 else f"${x:,.2f}"


def fmt_k(x):
    return f"{x/1000:,.1f}K" if x >= 1000 else f"{x:,.0f}"


def build_tweet():
    rows = []
    for sym in SYMS:
        rc, out = run([sys.executable, PHX, "market", "ticker", sym])
        if rc != 0:
            continue
        try:
            d = json.loads(out)["data"]
            px = float(d["mark_price"])
            chg = float(d.get("change_24h_pct") or 0)
            oi = float(d.get("open_interest") or 0)
            fr = float(d.get("funding_rate") or 0)
            rows.append(
                f"· {sym} {fmt_usd(px)} ({chg:+.1f}% 24h)"
                f" · OI {fmt_k(oi)} · fund {fr*100:+.4f}%"
            )
        except Exception:
            continue
    if len(rows) < 2:
        return None
    body = "Phoenix perps snapshot:\n" + "\n".join(rows)
    return f"{body}\n{FOOTER}" if FOOTER else body


def main() -> int:
    dry = "--dry-run" in sys.argv
    text = build_tweet()
    if not text:
        log("SKIP no venue data")
        print("no venue data; nothing posted")
        return 0
    if len(text) > 280:
        log(f"SKIP over-long ({len(text)} chars)")
        print("composed tweet exceeds 280 chars; not posted")
        return 1
    print(f"--- phoenix perps pulse ({len(text)} chars) ---")
    print(text)
    if dry:
        print("dry run: not posting")
        return 0
    rc, out = run([sys.executable, POST, "--text", text], timeout=60)
    print(out)
    if rc != 0:
        log(f"FAIL rc={rc}")
        return 1
    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
