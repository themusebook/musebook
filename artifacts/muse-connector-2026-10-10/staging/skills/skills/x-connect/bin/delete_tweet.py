#!/usr/bin/env python3
"""Delete a tweet by ID (X API v2, OAuth2 user context).

Usage:
    delete_tweet.py --id 2101689448744325230 [--dry-run]

Auth: stored ``custom.x`` OAuth2 credential via surrogate exchange
(same as post.py). Requires the app's token to carry tweet.write scope.
"""
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "/home/hatch/workspace/skills/x-connect/bin")
from tweet import API, x_request  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Tweet ID to delete")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    url = f"{API}/2/tweets/{args.id}"
    if args.dry_run:
        print(f"dry run: would DELETE {url}")
        return 0
    resp = x_request("DELETE", url, None)
    deleted = (resp.get("data") or {}).get("deleted", False)
    if deleted:
        print(f"deleted tweet {args.id}")
        return 0
    print(f"delete failed: {json.dumps(resp)[:500]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
