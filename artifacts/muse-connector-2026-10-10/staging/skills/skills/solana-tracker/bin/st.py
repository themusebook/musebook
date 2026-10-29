#!/usr/bin/env python3
"""Solana Tracker Data API CLI.

Usage:
  st.py <METHOD> <PATH> [--data JSON]

Examples:
  st.py GET /credits
  st.py GET "/tokens/latest?page=1"
  st.py GET "/tokens/<mint>"
  st.py GET "/price?token=<mint>"
  st.py POST "/price/multi" --data '{"tokens": ["<m1>", "<m2>"]}'

Auth: attaches the stored custom.solana-tracker credential via authd
surrogate exchange. Never prints the key.
"""
import sys
import json
import urllib.request
import urllib.parse

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://data.solanatracker.io"
ALLOWED = ["data.solanatracker.io"]
CRED = "custom.solana-tracker"


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
    req.add_header("User-Agent", "solana-tracker-skill/1.0")
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
            body = e.read().decode("utf-8", "replace")[:500]
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
