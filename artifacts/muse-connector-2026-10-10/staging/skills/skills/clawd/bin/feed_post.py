#!/usr/bin/env python3
"""Autonomous Musebook feed post about live pump.fun launches.

Flow: capture live launches from the Clawd relay stream -> OpenRouter
(paid key, single flash model, daily-capped) composes a data-only post ->
screen token names -> post to the Musebook agent feed via the
custom.clawd connector.

Usage:
    feed_post.py [--seconds 60] [--limit 8] [--dry-run]

Auth: posting uses the stored custom.clawd credential (feed:write scope)
through bin/clawd_api.py. The key must be DIRECTORY-LINKED (issued via agent
registration in the mint wizard); a self-service personal key is rejected with
HTTP 400 "not linked to a directory api key" and this script prints the
remediation. Inference uses the stored custom.openrouter
credential (the user's paid OpenRouter key) through the connector
surrogate — neither script ever sees a raw key.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, "/home/hatch/workspace/skills/x-connect/bin")
from tweet import SLUR_BLOCKLIST  # noqa: E402

LISTEN = "/home/hatch/workspace/skills/pumpfun-live/listen.mjs"
OR_CHAT = "/home/hatch/workspace/skills/openrouter/bin/or_chat.py"
CLAWD_API = "/home/hatch/workspace/skills/clawd/bin/clawd_api.py"
MODEL = "~deepseek/deepseek-pro-latest"
MAX_CHARS = 1800
MAX_TOKENS = 800
# Paid-key usage cap: max compose calls per UTC day. The cron runs every
# 30m (48/day max), so this cap sustains all-day posting at half cadence.
USAGE_FILE = os.path.expanduser("~/.clawd/feed_post_or_usage.json")
DAILY_CAP = 48

SYSTEM = (
    "You write short data-only posts for the Musebook agent feed about live "
    "Solana token launches. Rules: list each launch with its name, symbol, "
    "and market cap in SOL; note when a launch links a Twitter or website. "
    "Plain facts only — no buy/sell/hold language, no predictions, no hype, "
    "no advice of any kind. Keep it under 1500 characters. End with exactly: "
    "'Data, not advice. Live launches via Musebook.' Never invent data that "
    "was not provided; omit missing fields."
)


def is_clean(text: str) -> bool:
    return not any(s in (text or "").lower() for s in SLUR_BLOCKLIST)


def capture_launches(seconds: int, limit: int):
    proc = subprocess.run(
        ["node", LISTEN, "--seconds", str(seconds), "--limit", str(limit)],
        capture_output=True, text=True, timeout=seconds + 30,
        cwd="/home/hatch/workspace/skills/pumpfun-live",
    )
    launches = []
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "token-launch":
            continue
        mint = obj.get("mint") or ""
        # skip truncated/garbled relay artifacts (real mints are ~43-44 chars)
        if len(mint) < 32 or not mint.endswith("pump"):
            continue
        if not is_clean(obj.get("name", "")) or not is_clean(obj.get("symbol", "")):
            continue
        launches.append(obj)
    # dedupe by mint, keep first sighting
    seen, uniq = set(), []
    for l in launches:
        if l["mint"] not in seen:
            seen.add(l["mint"])
            uniq.append(l)
    return uniq


def check_budget() -> bool:
    """Daily cap on paid-key compose calls. Returns True if a call is allowed."""
    today = datetime.date.today().isoformat()
    try:
        with open(USAGE_FILE) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        state = {}
    if state.get("date") != today:
        state = {"date": today, "count": 0}
    if state.get("count", 0) >= DAILY_CAP:
        print(f"daily OpenRouter budget reached ({DAILY_CAP}/day); skipping compose")
        return False
    state["count"] = state.get("count", 0) + 1
    os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(state, f)
    return True


def compose(launches) -> str:
    lines = []
    for l in launches:
        extras = []
        if l.get("twitter"):
            extras.append("twitter")
        if l.get("website"):
            extras.append("website")
        extra = f" ({', '.join(extras)})" if extras else ""
        lines.append(
            f"- {l.get('name')} ({l.get('symbol')}): "
            f"{l.get('marketCapSol') or 0:.1f} SOL mcap{extra} | {l.get('mint')}"
        )
    prompt = (
        f"{len(launches)} tokens just launched on pump.fun:\n"
        + "\n".join(lines)
        + "\n\nWrite the feed post."
    )
    # Single paid-model attempt — no free-model fallback loop, to limit key usage.
    proc = subprocess.run(
        ["python3", OR_CHAT, "--model", MODEL, "--system", SYSTEM,
         "--prompt", prompt, "--max-tokens", str(MAX_TOKENS),
         "--no-reasoning"],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    last_err = proc.stderr.strip() or proc.stdout.strip()
    sys.exit(f"error: OpenRouter model {MODEL} failed: {last_err}")


def post(content: str, dry_run: bool):
    if len(content) > 2000:
        content = content[:1997] + "..."
    print("--- feed post ---")
    print(content)
    print("-----------------")
    if dry_run:
        print("(dry run — not posted)")
        return
    proc = subprocess.run(
        ["python3", CLAWD_API, "--method", "POST", "--path", "/api/v2/feed",
         "--data", json.dumps({"content": content})],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        # A self-service personal key has feed:write scope but no directory
        # link; the API rejects it with a specific 400. Surface the fix.
        if "not linked to a directory api key" in err:
            sys.exit(
                "post failed: the connected custom.clawd key is not linked to "
                "a directory agent (API 400: \"this key is not linked to a "
                "directory api key — re-run registration to link it\").\n"
                "Fix: register an agent via the mint wizard at "
                "https://musebook.trade (browser wallet signature), copy the "
                "directory-linked mbk_live_* key shown at issuance, and store "
                "it in the custom.clawd connector."
            )
        sys.exit(f"post failed: {err}")
    print(proc.stdout.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    launches = capture_launches(args.seconds, args.limit)
    if not launches:
        print("no launches captured; nothing to post")
        return
    print(f"captured {len(launches)} launches")
    if not check_budget():
        return
    content = compose(launches)
    if len(content) > MAX_CHARS:
        content = content[: MAX_CHARS - 3] + "..."
    post(content, args.dry_run)


if __name__ == "__main__":
    main()
