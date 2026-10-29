#!/usr/bin/env python3
"""Stonkfun public API CLI (no key, no signup).

Usage:
  stonk.py GET  <PATH>              e.g. /tokens?sort=newest&pageSize=5
  stonk.py POST <PATH> --data '<json>'

Examples:
  stonk.py GET "/tokens?sort=newest&pageSize=5"
  stonk.py GET /stats
  stonk.py GET /pairs?launchable=true
  stonk.py GET /tokens/{mint}/fees
  stonk.py POST /tokens/{mint}/fees/claim/prepare --data '{"creatorWallet":"..."}'
  stonk.py POST /tokens/{mint}/fees/claim/submit --data '{"creatorWallet":"...","intentId":"...","signedTransaction":"..."}'

NOTE: POST /launches/prepare is DISABLED platform-side (503). Launches go
through bin/stonk_launch.py (self-built LaunchLab path) — see SKILL.md.

Signing rule: prepare endpoints return UNSIGNED transactions. They must be
signed in the user's browser wallet — never locally, never here.
"""
import sys
import json
import urllib.request
import urllib.error

BASE = "https://www.stonkfun.xyz"


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
    if "/api/public" not in url and not url.startswith(BASE + "/api/public/total-assets"):
        # default to the versioned base path
        url = BASE + "/api/public/v1" + (path if path.startswith("/") else "/" + path)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "stonkfun-skill/1.0")
    req.add_header("accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:1200]
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
