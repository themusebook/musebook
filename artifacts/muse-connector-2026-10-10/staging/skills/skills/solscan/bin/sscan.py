#!/usr/bin/env python3
"""Solscan Pro API CLI (v2.0).

Generic authenticated passthrough: METHOD + PATH against
https://pro-api.solscan.io/v2.0. Prints the provider JSON verbatim.

Usage:
  sscan.py <METHOD> <PATH> [--data JSON]

Examples:
  sscan.py GET /chaininfo
  sscan.py GET "/account/transactions?account=<address>&limit=10"
  sscan.py GET "/token/meta?address=<mint>"
  sscan.py GET "/token/price?address=<mint>"
  sscan.py GET "/transaction/detail?tx=<signature>"

Auth: attaches the stored custom.solscan credential via authd surrogate
exchange. The provider reads the key from the `token` request header
(per the Pro API docs: `token`, not Bearer, not query param). Never prints
the key.
"""
import sys
import json
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://pro-api.solscan.io/v2.0"
ALLOWED = ["pro-api.solscan.io"]
CRED = "custom.solscan"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__.strip())
        return 2
    method = sys.argv[1].upper()
    path = sys.argv[2]
    data = None
    if "--data" in sys.argv:
        data = sys.argv[sys.argv.index("--data") + 1].encode()

    url = BASE + (path if path.startswith("/") else "/" + path)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "solscan-skill/1.0")
    try:
        add_surrogate_to_request(req, CRED, allowed_hosts=ALLOWED)
    except DynamicCredentialError as e:
        print(json.dumps({"ok": False, "error": f"credential: {e}"}))
        return 1
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        payload = read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:1000]
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
