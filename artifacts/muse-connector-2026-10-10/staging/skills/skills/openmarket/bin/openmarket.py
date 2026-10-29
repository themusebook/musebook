#!/usr/bin/env python3
"""OpenMarket (openmarket.xyz) unified data API CLI.

Usage:
  openmarket.py GET <PATH> [--param name=value] ...

Examples:
  openmarket.py GET /v1/points --param type=TRADE_SIDE_AGNOSTIC_AGG \\
    --param exchange=BINANCE_FUTURES --param rawSymbol=BTCUSDT \\
    --param interval=HOUR --param from=1774800000 --param period=3600

Auth: attaches the stored custom.openmarket credential as the
X-OpenMarket-Key header via authd surrogate exchange. Never prints the key.
"""
import sys
import json
import urllib.parse
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://api.openmarket.xyz"
ALLOWED = ["api.openmarket.xyz"]
CRED = "custom.openmarket"


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

    req = urllib.request.Request(url, method=method)
    req.add_header("Accept", "application/json")
    try:
        add_surrogate_to_request(req, CRED, allowed_hosts=ALLOWED)
    except DynamicCredentialError as e:
        print(f"AUTH ERROR: {e}", file=sys.stderr)
        return 3

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = read_json_response(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:2000]
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"REQUEST ERROR: {e}", file=sys.stderr)
        return 1

    print(json.dumps(data, indent=2)[:200000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
