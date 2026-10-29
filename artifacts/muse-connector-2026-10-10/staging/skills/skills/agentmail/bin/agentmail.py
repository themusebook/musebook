#!/usr/bin/env python3
"""Call the AgentMail REST API with the stored custom.agentmail credential.

The API key is attached as a surrogate Authorization: Bearer header by authd;
this script never sees the raw key. Authenticated requests are restricted to
api.agentmail.to.

Usage:
    agentmail.py list-inboxes
    agentmail.py list-messages --inbox-id <id> [--limit 10]
    agentmail.py get-message --inbox-id <id> --message-id <mid>
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    add_surrogate_to_request,
    read_json_response,
)

BASE = "https://api.agentmail.to/v0"
ALLOWED = ["api.agentmail.to"]
CREDENTIAL = "custom.agentmail"


def api_request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return read_json_response(resp)
    except DynamicCredentialError as exc:
        sys.exit(f"request error: {exc}")
    except Exception as exc:  # noqa: BLE001 - surface provider/network errors plainly
        sys.exit(f"api error: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-inboxes", help="List AgentMail inboxes")

    p = sub.add_parser("list-messages", help="List messages in an inbox")
    p.add_argument("--inbox-id", required=True)
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("get-message", help="Get one message with its body")
    p.add_argument("--inbox-id", required=True)
    p.add_argument("--message-id", required=True)

    args = ap.parse_args()

    if args.cmd == "list-inboxes":
        out = api_request("GET", "/inboxes")
    elif args.cmd == "list-messages":
        out = api_request("GET", f"/inboxes/{args.inbox_id}/messages?limit={args.limit}")
    elif args.cmd == "get-message":
        out = api_request("GET", f"/inboxes/{args.inbox_id}/messages/{args.message_id}")

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
