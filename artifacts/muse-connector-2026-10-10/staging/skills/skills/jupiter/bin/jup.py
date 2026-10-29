#!/usr/bin/env python3
"""Jupiter API CLI.

Usage:
  jup.py GET <PATH>          (e.g. /price/v3?ids=<mint>)
  jup.py POST <PATH> --data '<json>'

Examples:
  jup.py GET "/price/v3?ids=So11111111111111111111111111111111111111112"
  jup.py GET "/swap/v2/order?inputMint=...&outputMint=...&amount=...&taker=<browser-wallet-pubkey>"
  jup.py POST /swap/v2/execute --data '{"signedTransaction":"<base64-from-browser>","requestId":"<from-order>"}'

Auth: attaches the stored custom.jupiter credential via authd surrogate
exchange (x-api-key header). Never prints the key.

Browser-signed swap flow (no local wallet, no local signing):
  1. GET /swap/v2/order with taker=<user browser wallet> -> returns base64 v0 tx + requestId
  2. User's browser wallet signs the tx (fresh confirmation per swap)
  3. POST /swap/v2/execute with signedTransaction + requestId
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

BASE = "https://api.jup.ag"
ALLOWED = ["api.jup.ag"]
CRED = "custom.jupiter"


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
    req.add_header("User-Agent", "jupiter-skill/1.0")
    req.add_header("accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
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
