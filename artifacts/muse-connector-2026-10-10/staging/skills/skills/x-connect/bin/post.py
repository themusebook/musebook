#!/usr/bin/env python3
"""Post a plain-text Musebook tweet, optionally with an image.

Usage:
    post.py --text "..." [--image art.png] [--dry-run]

Auth: stored ``custom.x`` OAuth2 credential via surrogate exchange.
Never prints or persists raw credentials. Enforces the 280-char limit and
the slur blocklist shared with tweet.py.
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "/home/hatch/workspace/skills/x-connect/bin")
from tweet import (  # noqa: E402
    MAX_TWEET,
    SLUR_BLOCKLIST,
    is_clean,
    post_tweet,
    upload_media,
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--image")
    ap.add_argument("--reply-to", default=None,
                    help="Tweet ID to reply to (adds reply.in_reply_to_tweet_id)")
    ap.add_argument("--quote", default=None,
                    help="Tweet ID to quote (adds quote_tweet_id)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    text = args.text.strip()
    if len(text) > MAX_TWEET:
        print(f"text is {len(text)} chars; exceeds {MAX_TWEET}", file=sys.stderr)
        return 1
    if not is_clean(text):
        print("text failed blocklist screen; refusing to post", file=sys.stderr)
        return 1
    print(f"--- tweet ({len(text)} chars) ---")
    print(text)
    print("-------------------------------")
    if args.dry_run:
        print("dry run: not uploading, not posting")
        return 0

    media_id = upload_media(args.image) if args.image else None
    if media_id:
        print(f"media_id: {media_id}")
    if args.reply_to or args.quote:
        from tweet import x_request, API  # noqa: E402
        payload = {"text": text}
        if media_id:
            payload["media"] = {"media_ids": [media_id]}
        if args.reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": str(args.reply_to)}
        if args.quote:
            payload["quote_tweet_id"] = str(args.quote)
        resp = x_request("POST", f"{API}/2/tweets", payload)
    else:
        resp = post_tweet(text, [media_id] if media_id else None)
    tid = (resp.get("data") or {}).get("id")
    if not tid:
        import json

        print(f"tweet failed: {json.dumps(resp)[:500]}", file=sys.stderr)
        return 1
    print(f"posted: https://x.com/i/status/{tid}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
