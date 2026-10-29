#!/usr/bin/env python3
"""Massive (massive.com) Stocks API CLI — formerly Polygon.io.

Usage:
  massive.py GET <PATH> [--param name=value] ...

Examples:
  massive.py GET /v1/marketstatus/now
  massive.py GET /v2/aggs/ticker/AAPL/prev
  massive.py GET /v3/reference/tickers --param ticker=AAPL --param limit=1
  massive.py GET '/v2/aggs/ticker/AAPL/range/1/day/2026-09-01/2026-09-23'

Auth: attaches the stored custom.massive credential via authd surrogate
exchange as the ?apiKey= query param. Never prints the key.
"""
import sys
import json
import urllib.parse
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    url_with_surrogate_query_param,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://api.massive.com"
ALLOWED = ["api.massive.com"]
CRED = "custom.massive"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__.strip())
        return 2
    method = sys.argv[1].upper()
    path = sys.argv[2]
    extra_params = []
    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--param" and i + 1 < len(args):
            name, _, value = args[i + 1].partition("=")
            extra_params.append((name.strip(), value.strip()))
            i += 2
        else:
            i += 1

    url = BASE + (path if path.startswith("/") else "/" + path)
    if extra_params:
        sep = "&" if "?" in url else "?"
        url += sep + "&".join(
            f"{urllib.parse.quote(n, safe='')}={urllib.parse.quote(v, safe='')}"
            for n, v in extra_params
        )
    try:
        url = url_with_surrogate_query_param(url, CRED, allowed_hosts=ALLOWED)
    except DynamicCredentialError as e:
        print(json.dumps({"ok": False, "error": f"credential: {e}"}))
        return 1
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "massive-skill/1.0")
    req.add_header("accept", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
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
