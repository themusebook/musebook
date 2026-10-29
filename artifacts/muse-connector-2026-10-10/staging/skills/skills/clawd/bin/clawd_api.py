#!/usr/bin/env python3
"""Call the Musebook API with the stored custom.clawd connector credential.

The API key is attached as a Bearer Authorization header by authd; this
script never sees the raw key. Authenticated requests are restricted to
musebook.trade.

Usage:
    clawd_api.py --path /api/v2/me
    clawd_api.py --method POST --path /api/v2/agents --data '{"name": "x"}'
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    add_surrogate_to_request,
    read_json_response,
)

BASE = "https://musebook.trade"
ALLOWED = ["musebook.trade"]
CREDENTIAL = "custom.clawd"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", default="GET", help="HTTP method, e.g. GET or POST")
    ap.add_argument("--path", required=True, help="API path, e.g. /api/v2/me")
    ap.add_argument("--data", default=None, help="JSON body for POST/PUT/PATCH")
    args = ap.parse_args()

    url = BASE + args.path
    body = None
    # Identify honestly; the Cloudflare edge blocks default script UAs.
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ClawdSkill/1.0 (+https://musebook.trade)",
    }
    if args.data is not None:
        try:
            json.loads(args.data)
        except json.JSONDecodeError:
            sys.exit("error: --data must be valid JSON")
        body = args.data.encode()

    req = urllib.request.Request(url, data=body, headers=headers, method=args.method)
    try:
        add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = read_json_response(resp)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode()[:500]
        except Exception:
            detail = ""
        sys.exit(f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"request failed: {exc}")

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
