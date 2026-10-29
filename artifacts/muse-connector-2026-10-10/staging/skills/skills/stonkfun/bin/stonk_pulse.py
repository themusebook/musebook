#!/usr/bin/env python3
"""Stonkfun pulse: surface the newest stonk.fun token launches and tweet them.

Reads the public stonkfun API (no key, no signup), finds tokens not yet seen,
ranks them, and posts ONE data-only tweet (prices/facts only — no advice
language). If nothing is new since the last run, it stays silent (no spam).

Usage:
  stonk_pulse.py [--dry-run] [--top 3] [--page-size 25]

State: ~/workspace/skills/stonkfun/state/stonk_pulse_state.json
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

API = "https://www.stonkfun.xyz/api/public/v1"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE, "state", "stonk_pulse_state.json")
POST_PY = "/home/hatch/workspace/skills/x-connect/bin/post.py"


def api_get(path):
    # NOTE (2026-09-19): urllib/http.client consistently gets truncated
    # responses from this API edge (http.client.IncompleteRead), while curl
    # completes reliably; fetch via curl subprocess instead.
    p = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-w", "\n%{http_code}",
         "-A", "clawd-stonk-pulse/1.0", API + path],
        capture_output=True, text=True, timeout=40)
    out = p.stdout.rsplit("\n", 1)
    code = int(out[1]) if len(out) == 2 and out[1].strip().isdigit() else 0
    if code == 429:
        raise RuntimeError("stonkfun rate-limited (429)")
    body = json.loads(out[0])
    return body.get("data", body)


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"seen_mints": [], "tweets": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def fmt_usd(v):
    v = float(v or 0)
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def token_line(t, cashtag=True):
    sym = (t.get("symbol") or "?").strip().lstrip("$")
    name = " ".join((t.get("name") or "").split())  # collapse whitespace/newlines
    if len(name) > 40:
        name = name[:37] + "..."
    mcap = fmt_usd((t.get("market") or {}).get("marketCapUsd", 0))
    grad = int(round(float(t.get("graduationProgress") or 0) * 100))
    # X limits posts to ONE cashtag ($SYMBOL); only the first token keeps it
    sym_disp = f"${sym}" if cashtag else sym
    label = f"{sym_disp} ({name})" if name and name.lower() != sym.lower() else sym_disp
    return f"{label} — {mcap} mcap, {grad}% graduated"


def compose(tweets_tokens):
    def build(toks):
        lines = ["\U0001f99e stonk.fun fresh launches:", ""]
        lines += [token_line(t, cashtag=(i == 0)) for i, t in enumerate(toks)]
        lines += ["", "watching on stonkfun.xyz"]
        return "\n".join(lines)

    text = build(tweets_tokens)
    # hard cap: drop trailing token lines until it fits
    while len(text) > 275 and len(tweets_tokens) > 1:
        tweets_tokens = tweets_tokens[:-1]
        text = build(tweets_tokens)
    return text, tweets_tokens


def post_tweet(text):
    out = subprocess.run(
        [sys.executable, POST_PY, "--text", text],
        capture_output=True, text=True, timeout=120,
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--page-size", type=int, default=25)
    args = ap.parse_args()

    data = api_get(f"/tokens?sort=newest&pageSize={args.page_size}")
    tokens = data.get("tokens", []) if isinstance(data, dict) else []
    if not tokens:
        print(json.dumps({"ok": False, "error": "no tokens returned"}))
        return 1

    state = load_state()
    seen = set(state.get("seen_mints", []))
    new = [t for t in tokens if t.get("mint") not in seen]

    # rank: newest first (the API already returns sort=newest), then
    # graduation progress, mcap, 24h volume as tiebreaks
    def rank_key(t):
        m = t.get("market") or {}
        try:
            ts = dt.datetime.fromisoformat(
                (t.get("createdAt") or "").replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            ts = 0.0
        return (
            ts,
            float(t.get("graduationProgress") or 0),
            float(m.get("marketCapUsd") or 0),
            float(m.get("volume24hUsd") or 0),
        )

    new.sort(key=rank_key, reverse=True)
    pick = new[: args.top]

    result = {
        "ok": True,
        "fetched": len(tokens),
        "new": len(new),
        "tweeted": 0,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    if not pick:
        print(json.dumps(result))
        return 0

    text, pick = compose(pick)
    result["tweet_text"] = text
    result["tweet_chars"] = len(text)

    if args.dry_run:
        print(json.dumps(result, indent=2))
        return 0

    out = post_tweet(text)
    tail = (out.stdout or "") + (out.stderr or "")
    url = None
    for line in tail.splitlines():
        line = line.strip()
        if line.startswith("posted:"):
            url = line.split("posted:", 1)[1].strip()
    result["post_exit"] = out.returncode
    result["tweet_url"] = url

    if out.returncode == 0 and url:
        result["tweeted"] = len(pick)
        state["seen_mints"] = list(seen | {t.get("mint") for t in tokens})
        state["seen_mints"] = state["seen_mints"][-500:]
        state.setdefault("tweets", []).append({
            "at": result["generated_at"],
            "url": url,
            "mints": [t.get("mint") for t in pick],
        })
        save_state(state)
    else:
        # don't mark as seen on failure — a retry should surface them again
        print(json.dumps({**result, "post_output_tail": tail[-500:]}))
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
