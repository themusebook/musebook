#!/usr/bin/env python3
"""Scalar platform API CLI (login portals).

Uses the stored custom.scalar connector credential via surrogate exchange.
Never prints or persists raw credentials.
"""
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://access.scalar.com"
CRED = "custom.scalar"
ALLOWED = ("access.scalar.com",)


def _request(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, CRED, allowed_hosts=ALLOWED)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return read_json_response(resp)


def cmd_list(_args):
    print(json.dumps(_request("GET", "/v1/login-portals"), indent=2))


def cmd_get(args):
    slug = args[0]
    print(json.dumps(_request("GET", f"/v1/login-portals/{slug}"), indent=2))


def cmd_set_favicon(args):
    slug, url = args[0], args[1]
    result = _request("PATCH", f"/v1/login-portals/{slug}", {"page": {"favicon": url}})
    print(json.dumps(result, indent=2))


COMMANDS = {
    "portals-list": cmd_list,
    "portals-get": cmd_get,
    "portals-set-favicon": cmd_set_favicon,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: {sys.argv[0]} {'|'.join(COMMANDS)} [...]", file=sys.stderr)
        sys.exit(2)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except DynamicCredentialError as e:
        print(f"credential error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
