#!/usr/bin/env python3
"""Token/project narrative tweet rotator.

Posts ONE text-only tweet per run from a rotating set defined by YOU in
rotation.json next to this script:

    { "tweets": ["first tweet (<=280 chars)", "second tweet", ...] }

Use it for a steady drumbeat about your token, product, or project —
vision and facts, never buy/sell recommendations, advice language, or
price targets.

Posts via the x-connect post.py (blocklist + 280-char enforced).
If X rejects a slot as duplicate content, the rotation advances past it
instead of wedging forever.

Portable: resolves the x-connect bin from $SKILLS_DIR or ~/.muse/skills.

Run once per schedule fire, e.g. hourly:
    python3 token_rotation_tweet.py
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.expanduser("~/.muse/skills"))
ROTATION = os.path.join(HERE, "rotation.json")
STATE = os.path.join(HERE, "token_rotation_state.json")
LOG = os.path.join(HERE, "token_rotation_runs.log")
POST = os.path.join(SKILLS_DIR, "x-connect", "bin", "post.py")

EXAMPLE = """{ "tweets": [
  "What we're building and why it matters. One factual line.",
  "A real surface, integration, or milestone your project shipped."
] }"""


def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception as e:
        return 1, "", f"ERR {e}"


def load_rotation():
    try:
        with open(ROTATION) as f:
            tweets = json.load(f)["tweets"]
    except FileNotFoundError:
        sys.exit(
            f"error: {ROTATION} not found.\n"
            f"Create it with your tweet rotation, e.g.:\n{EXAMPLE}"
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        sys.exit(f"error: {ROTATION} is not valid (need {{\"tweets\": [...]}}): {e}")
    if not isinstance(tweets, list) or not tweets:
        sys.exit(f"error: {ROTATION} needs a non-empty \"tweets\" list.")
    return tweets


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


def main():
    tweets = load_rotation()
    for i, t in enumerate(tweets):
        if len(t) > 280:
            print(f"TWEET {i} OVER LENGTH: {len(t)} chars", file=sys.stderr)
            sys.exit(2)
    state = load_state()
    idx = state.get("idx", 0) % len(tweets)
    text = tweets[idx]
    rc, out, err = run([sys.executable, POST, "--text", text], timeout=90)
    if rc != 0:
        # X rejected this text as a duplicate of an earlier post. The text has
        # already gone out, so don't wedge the rotation on it: advance the
        # index and log the skip instead of failing forever on one slot.
        if "duplicate content" in (err or out):
            log(f"POST SKIP idx={idx} duplicate content; advancing")
            state["idx"] = (idx + 1) % len(tweets)
            state["last_url"] = f"SKIP duplicate idx={idx}"
            save_state(state)
            print(f"Skipped idx={idx} (duplicate content); advanced to idx={state['idx']}")
            sys.exit(0)
        log(f"POST FAIL idx={idx} rc={rc} out={out!r} err={err!r}")
        print(f"Post failed (tweet {idx}): {err or out}", file=sys.stderr)
        sys.exit(1)
    log(f"POST OK idx={idx} url={out}")
    state["idx"] = (idx + 1) % len(tweets)
    state["last_url"] = out
    save_state(state)
    print(out)


if __name__ == "__main__":
    main()
