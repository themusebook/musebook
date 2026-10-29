#!/usr/bin/env python3
"""Post a $CLAWD buy announcement tweet, then reply to it with the Solscan link.

Auth: stored ``custom.x`` OAuth2 credential via surrogate exchange.
Never prints or persists raw credentials.

Usage:
    buy_tweet.py --image art.png --clawd 15689.85 --sol 0.0169 --tx <sig>
"""
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "/home/hatch/workspace/skills/x-connect/bin")
import tweet  # noqa: E402

MAX_TWEET = 280


def compose_main(clawd: str, sol: str) -> str:
    return (
        f"Just bought {clawd} $CLAWD for {sol} SOL 🦞\n"
        f"Stacking the lobster bags. Track every buy live at musebook.trade"
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--clawd", required=True)
    ap.add_argument("--sol", required=True)
    ap.add_argument("--tx", required=True)
    ap.add_argument("--text", default=None,
                    help="Override the composed tweet text (must still fit 280 chars)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    text = a.text if a.text else compose_main(a.clawd, a.sol)
    if len(text) > MAX_TWEET:
        raise SystemExit(f"tweet too long: {len(text)} chars")
    reply = f"Solscan tx: https://solscan.io/tx/{a.tx}"
    if len(reply) > MAX_TWEET:
        raise SystemExit(f"reply too long: {len(reply)} chars")

    if a.dry_run:
        print(json.dumps({"tweet": text, "reply": reply, "image": a.image}, indent=2))
        return 0

    media_id = tweet.upload_media(a.image)
    posted = tweet.post_tweet(text, [media_id])
    tweet_id = (posted.get("data") or {}).get("id")
    if not tweet_id:
        raise RuntimeError(f"tweet post failed: {json.dumps(posted)[:300]}")
    reply_resp = tweet.x_request(
        "POST",
        f"{tweet.API}/2/tweets",
        {"text": reply, "reply": {"in_reply_to_tweet_id": str(tweet_id)}},
    )
    reply_id = (reply_resp.get("data") or {}).get("id")
    print(json.dumps({
        "tweet_id": tweet_id,
        "tweet_url": f"https://x.com/i/status/{tweet_id}",
        "reply_id": reply_id,
        "reply_url": f"https://x.com/i/status/{reply_id}" if reply_id else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
