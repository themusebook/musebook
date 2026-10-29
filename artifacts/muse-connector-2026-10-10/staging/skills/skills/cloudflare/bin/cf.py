#!/usr/bin/env python3
"""Call the Cloudflare v4 API with the stored custom.cloudflare credential.

The API token is attached as a surrogate header by authd; this script
never sees the raw key. Authenticated requests are restricted to
api.cloudflare.com.

Usage:
    cf.py --method GET --path /accounts
    cf.py --method POST --path /accounts/{id}/pages/projects \
        --data '{"name":"musebook","production_branch":"main"}'
    cf.py --method GET --path /accounts/{id}/pages/projects --params '{"per_page":"100"}'
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    add_surrogate_to_request,
    read_json_response,
)

BASE = "https://api.cloudflare.com/client/v4"
ALLOWED = ["api.cloudflare.com"]
CREDENTIAL = "custom.cloudflare"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", default="GET")
    ap.add_argument("--path", required=True, help="API path, e.g. /accounts")
    ap.add_argument("--params", default="{}",
                    help="JSON object of query params")
    ap.add_argument("--data", default=None,
                    help="JSON request body (object or array)")
    args = ap.parse_args()

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError:
        sys.exit("error: --params must be valid JSON")
    if not isinstance(params, dict):
        sys.exit("error: --params must be a JSON object")

    url = BASE + args.path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = None
    headers = {"Accept": "application/json"}
    if args.data is not None:
        try:
            json.loads(args.data)
        except json.JSONDecodeError:
            sys.exit("error: --data must be valid JSON")
        data = args.data.encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers,
                                 method=args.method.upper())
    try:
        add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = read_json_response(resp)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            body = "<unreadable body>"
        sys.exit(f"HTTP {exc.code} on {args.method} {args.path}:\n{body}")

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
