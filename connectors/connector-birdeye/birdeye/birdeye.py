#!/usr/bin/env python3
"""BirdEye Data API CLI.

Usage:
  birdeye.py GET <PATH> [--header 'Name: Value'] ...

Examples:
  birdeye.py GET /defi/price --header 'x-chain: solana' --data ...
  birdeye.py GET '/perps/v1/token/list?time_frame=all&sort_by=open_interest&sort_type=desc&limit=10' --header 'x-perp: hyperliquid'
  birdeye.py GET /perps/v1/token/overview --header 'x-perp: hyperliquid'

Auth: attaches the stored custom.birdeye credential via authd surrogate
exchange (X-API-KEY header). Never prints the key.
"""
import sys
import json
import urllib.request
import urllib.error


BASE = "https://public-api.birdeye.so"
ALLOWED = ["public-api.birdeye.so"]
CRED = "custom.birdeye"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__.strip())
        return 2
    method = sys.argv[1].upper()
    if method != 'GET':
        print(json.dumps({'ok': False, 'error': 'read_only: only GET is supported'}))
        return 2
    sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
    from dynamic_credentials import (
        add_surrogate_to_request,
        read_json_response,
        DynamicCredentialError,
    )
    
    path = sys.argv[2]
    headers = {}
    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--header" and i + 1 < len(args):
            name, _, value = args[i + 1].partition(":")
            headers[name.strip()] = value.strip()
            i += 2
        else:
            i += 1

    if any(name.lower() in ['authorization', 'x-api-key'] for name in headers):
        print(json.dumps({'ok': False, 'error': 'Use the stored connector credential'}))
        return 2
    url = BASE + (path if path.startswith("/") else "/" + path)
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "birdeye-skill/1.0")
    req.add_header("accept", "application/json")
    for name, value in headers.items():
        req.add_header(name, value)
    try:
        add_surrogate_to_request(req, CRED, allowed_hosts=ALLOWED)
    except DynamicCredentialError as e:
        print(json.dumps({"ok": False, "error": f"credential: {e}"}))
        return 1
    try:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        resp = urllib.request.build_opener(NoRedirect).open(req, timeout=30)
        payload = read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:800]
        except Exception:
            body = "<unreadable>"
        print(json.dumps({"ok": False, "error": f"HTTP {e.code}", "body": body}))
        return 1
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 1
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
