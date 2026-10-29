#!/usr/bin/env python3
"""Surrogate-authenticated Telegram Bot API caller.

Usage: tg_api.py METHOD [payload.json|-]
Reads payload from a JSON file arg or stdin. Prints response JSON.
Auth: custom.telegram credential via authd surrogate exchange (never reads the token).
The token is injected into the URL path: https://api.telegram.org/bot<token>/METHOD
"""
import json
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry, read_json_response

BASE_TEMPLATE = "https://api.telegram.org/bot{}/"
ALLOWED_HOSTS = ["api.telegram.org"]


def surrogate_url(method_name):
    """Build the Bot API URL with the raw surrogate in the path.

    NOTE: the surrogate must NOT be URL-encoded — the egress proxy matches
    the raw `hsurr:...` string to swap in the real token. `:` is legal in a
    URL path segment, so raw insertion is safe.
    """
    import urllib.parse

    entry = dynamic_credential_entry("custom.telegram", "access_token")
    placement = entry.get("placement")
    if not (isinstance(placement, dict) and "url_path_segment" in placement):
        raise RuntimeError(f"custom.telegram is not url_path_segment: {placement!r}")
    host = (urllib.parse.urlparse(BASE_TEMPLATE).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise RuntimeError(f"refusing URL with host {host}")
    surrogate = str(entry["surrogate"]).strip()
    if not surrogate.startswith("hsurr:"):
        raise RuntimeError("authd returned a non-surrogate value")
    return BASE_TEMPLATE.replace("{}", surrogate, 1) + method_name


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: tg_api.py METHOD [payload.json|-]")
    method_name = sys.argv[1]
    payload = None
    if len(sys.argv) > 2:
        raw = sys.stdin.read() if sys.argv[2] == "-" else open(sys.argv[2]).read()
        payload = json.loads(raw)
    url = surrogate_url(method_name)
    if payload is not None:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST"
        )
        req.add_header("Content-Type", "application/json")
    else:
        req = urllib.request.Request(url, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        sys.exit(f"Telegram API {method_name} -> HTTP {e.code}: {detail}")
    print(json.dumps(read_json_response(resp), indent=2))


if __name__ == "__main__":
    main()
