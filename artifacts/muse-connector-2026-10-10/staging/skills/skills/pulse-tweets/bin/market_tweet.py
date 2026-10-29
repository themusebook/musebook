#!/usr/bin/env python3
"""Rotating market-data tweet pulse.

Rotates through venues, posting factual market data to X:
  phoenix -> jupiter -> dflow -> imperial -> ...

Each run picks the first venue in rotation order that yields fresh data,
posts ONE tweet via the x-connect post.py (blocklist + 280-char enforced),
then advances the rotation.

Content is prices/data only: no recommendations, no signals, no advice
language. Never touches wallets or trading.

Portable: resolves sibling skill bins from $SKILLS_DIR or ~/.muse/skills.
Set $PULSE_FOOTER for your own tagline (default: no footer).

Run once per schedule fire, e.g. hourly:
    python3 market_tweet.py [--dry-run]
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.expanduser("~/.muse/skills"))
STATE = os.path.join(HERE, "state.json")
LOG = os.path.join(HERE, "runs.log")
PHX = os.path.join(SKILLS_DIR, "phoenix", "bin", "phx.py")
JUP = os.path.join(SKILLS_DIR, "jupiter", "bin", "jup_predict.py")
DFLOW = os.path.join(SKILLS_DIR, "dflow", "bin", "dflow_quote.py")
POST = os.path.join(SKILLS_DIR, "x-connect", "bin", "post.py")
IMPERIAL_API = "https://api.imperial.space"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
FOOTER = os.environ.get("PULSE_FOOTER", "").strip()

VENUES = ["phoenix", "jupiter", "dflow", "imperial"]
# Phoenix gets every other run (boosted presence); the rest rotate on odd runs.
ROTATE = ["jupiter", "dflow", "imperial"]


def run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except Exception as e:
        return 1, f"ERR {e}"


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {"idx": 0}


def save_state(s):
    with open(STATE, "w") as f:
        json.dump(s, f)


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"{ts} {msg}\n")


def fmt_usd(x, dec=2):
    return f"${x:,.{dec}f}"


def fmt_pct(x):
    return f"{x:+.1f}%"


def with_footer(body):
    return f"{body}\n{FOOTER}" if FOOTER else body


def phoenix_tweet():
    parts = []
    for sym in ("BTC", "SOL", "ETH"):
        rc, out = run([sys.executable, PHX, "market", "ticker", sym])
        if rc != 0:
            continue
        try:
            d = json.loads(out)["data"]
            px = float(d["mark_price"])
            chg = float(d.get("change_24h_pct") or 0)
            dec = 0 if px >= 1000 else 2
            parts.append(f"{sym} {fmt_usd(px, dec)} ({fmt_pct(chg)} 24h)")
        except Exception:
            continue
    if len(parts) < 2:
        return None
    body = "Perps prices live on Phoenix:\n" + "\n".join("· " + p for p in parts)
    return with_footer(body)


def jupiter_tweet():
    rc, out = run([sys.executable, JUP, "events", "--provider", "bisonfi",
                   "--category", "crypto", "--tag", "15m", "--limit", "10"])
    if rc != 0:
        return None
    try:
        evs = json.loads(out)["events"]
    except Exception:
        return None
    for e in evs:
        mkts = {m.get("marketId", "").rsplit("-", 1)[-1]: m for m in e.get("markets", [])}
        up, down = mkts.get("UP"), mkts.get("DOWN")
        if not (up and down and up.get("tradable") and down.get("tradable")):
            continue
        try:
            up_c = float(up["buyYesUsd"]) / 10_000
            dn_c = float(down["buyYesUsd"]) / 10_000
            close = int(up.get("closeTime") or 0)
            close_s = datetime.fromtimestamp(close, tz=timezone.utc).strftime("%H:%M UTC")
            body = (f"BTC 15m Forecast (Jupiter):\n"
                    f"· UP {up_c:.0f}c\n· DOWN {dn_c:.0f}c\n"
                    f"Round closes ~{close_s}.")
            return with_footer(body)
        except Exception:
            continue
    return None


def dflow_tweet():
    rc, out = run([sys.executable, DFLOW, SOL_MINT, USDC_MINT, "1000000000"])
    if rc != 0:
        return None
    try:
        px = None
        for line in out.splitlines():
            if line.startswith("outAmount:"):
                px = float(line.split(":")[1].strip()) / 1_000_000
        if px is None:
            return None
        body = f"SOL {fmt_usd(px)} via DFlow spot quote (1 SOL to USDC)."
        return with_footer(body)
    except Exception:
        return None


def imperial_tweet():
    # Public read endpoints only — no JWT needed. Shows the router's
    # multi-venue mark prices for one asset, factual and neutral.
    try:
        req = urllib.request.Request(IMPERIAL_API + "/api/v1/mark-prices",
                                     headers={"User-Agent": "pulse-tweets/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception:
        return None
    rows = {row.get("symbol"): row for row in data.get("rows", [])}
    for sym in ("SOL", "BTC"):
        row = rows.get(sym)
        if not row:
            continue
        lines = []
        for venue in ("phoenix", "gmtrade", "index"):
            e = row.get(venue) or {}
            try:
                px = float(e["price"])
            except (KeyError, TypeError, ValueError):
                continue
            dec = 0 if px >= 1000 else 2
            lines.append(f"· {venue} {fmt_usd(px, dec)}")
        if len(lines) < 2:
            continue
        body = f"{sym} marks via Imperial:\n" + "\n".join(lines)
        return with_footer(body)
    return None


BUILDERS = {"phoenix": phoenix_tweet, "jupiter": jupiter_tweet,
            "dflow": dflow_tweet, "imperial": imperial_tweet}


def main() -> int:
    dry = "--dry-run" in sys.argv
    st = load_state()
    runs = st.get("runs", 0)
    text, venue = None, None
    # Even runs: Phoenix (boosted). Odd runs: rotate the other venues.
    if runs % 2 == 0:
        text, venue = phoenix_tweet(), "phoenix"
    if not text:
        start = st.get("idx", 0) % len(ROTATE)
        for i in range(len(ROTATE)):
            v = ROTATE[(start + i) % len(ROTATE)]
            t = BUILDERS[v]()
            if t:
                text, venue = t, v
                st["idx"] = (ROTATE.index(v) + 1) % len(ROTATE)
                break
    st["runs"] = runs + 1
    if not text:
        log("SKIP no venue yielded data")
        print("no venue yielded data; nothing posted")
        return 0
    save_state(st)
    if len(text) > 280:
        log(f"SKIP over-long ({len(text)} chars) venue={venue}")
        print("composed tweet exceeds 280 chars; not posted")
        return 1
    print(f"--- venue: {venue} ({len(text)} chars) ---")
    print(text)
    if dry:
        print("dry run: not posting")
        return 0
    rc, out = run([sys.executable, POST, "--text", text], timeout=60)
    print(out)
    if rc != 0:
        log(f"FAIL venue={venue} rc={rc}")
        return 1
    log(f"OK venue={venue}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
