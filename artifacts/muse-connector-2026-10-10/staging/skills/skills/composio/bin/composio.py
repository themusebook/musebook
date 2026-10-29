#!/usr/bin/env python3
"""Composio API CLI (REST v3.1). Auth via the user-connected custom.composio
credential (stored in the Secure Vault, attached through the authd surrogate
exchange). Never prints, logs, or persists raw credentials."""
import json
import sys
import urllib.request
import urllib.parse

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

BASE = "https://backend.composio.dev/api/v3.1"
HOSTS = ["backend.composio.dev"]
CRED = "custom.composio"


def api(method, path, body=None, query=None):
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:2000]
        except Exception:
            detail = ""
        print(f"HTTP {e.code}: {detail}", file=sys.stderr)
        sys.exit(2)


def show(obj):
    print(json.dumps(obj, indent=2)[:8000])


def cmd_toolkits(args):
    out = api("GET", "/toolkits", query={"limit": args.get("limit") or 50} or None)
    items = out.get("items", out if isinstance(out, list) else [])
    for t in items:
        print(f"{t.get('slug')}\t{t.get('name')}\t{t.get('type')}")
    return items


def cmd_toolkit(args):
    out = api("GET", f"/toolkits/{args['slug']}")
    show(out)
    return out


def cmd_sync(args):
    out = api("POST", "/custom/toolkits/sync", body={"slug": args["slug"]})
    show(out)
    return out


def cmd_tools(args):
    q = {"toolkit_slug": args["toolkit"]} if args.get("toolkit") else {}
    out = api("GET", "/tools", query=q or None)
    items = out.get("items", out if isinstance(out, list) else [])
    for t in items:
        print(f"{t.get('slug')}\t{t.get('name')}")
    return items


def cmd_accounts(args):
    q = {}
    if args.get("user_id"):
        q["user_id"] = args["user_id"]
    out = api("GET", "/connected_accounts", query=q or None)
    items = out.get("items", out if isinstance(out, list) else [])
    for a in items:
        print(f"{a.get('id')}\t{a.get('toolkit', {}).get('slug')}\t{a.get('status')}")
    return items


def cmd_auth_configs(args):
    q = {}
    if args.get("toolkit"):
        q["toolkit_slug"] = args["toolkit"]
    out = api("GET", "/auth_configs", query=q or None)
    items = out.get("items", out if isinstance(out, list) else [])
    for c in items:
        print(f"{c.get('id')}\t{c.get('toolkit', {}).get('slug')}\t{c.get('auth_scheme')}\t{c.get('status')}")
    return items


def cmd_connect(args):
    """Start the OAuth/API-key connect flow. Prints the redirect URL the user
    must open in their browser to authorize the connection."""
    body = {"auth_config_id": args["auth_config_id"], "user_id": args["user_id"]}
    if args.get("callback_url"):
        body["callback_url"] = args["callback_url"]
    out = api("POST", "/connected_accounts/link", body=body)
    show(out)
    return out


def cmd_execute(args):
    body = {
        "user_id": args["user_id"],
        "arguments": json.loads(args.get("args") or "{}"),
    }
    out = api("POST", f"/tools/execute/{args['tool']}", body=body)
    show(out)
    return out


def main():
    import argparse
    p = argparse.ArgumentParser(prog="composio.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("toolkits", help="list available toolkits")
    s.add_argument("--limit", type=int, default=50)
    s = sub.add_parser("toolkit", help="get toolkit detail by slug")
    s.add_argument("slug")
    s = sub.add_parser("sync", help="sync a custom toolkit's tool definitions")
    s.add_argument("slug")
    s = sub.add_parser("tools", help="list tools, optionally for one toolkit")
    s.add_argument("--toolkit")
    s = sub.add_parser("accounts", help="list connected accounts")
    s.add_argument("--user-id")
    s = sub.add_parser("auth_configs", help="list auth configs, optionally for one toolkit")
    s.add_argument("--toolkit")
    s = sub.add_parser("connect", help="start the connect flow for an auth config")
    s.add_argument("--auth-config-id", required=True)
    s.add_argument("--user-id", required=True)
    s.add_argument("--callback-url")
    s = sub.add_parser("execute", help="execute a tool")
    s.add_argument("--tool", required=True)
    s.add_argument("--user-id", required=True)
    s.add_argument("--args", default="{}")
    ns = p.parse_args()
    {"toolkits": cmd_toolkits, "toolkit": cmd_toolkit, "sync": cmd_sync,
     "tools": cmd_tools, "accounts": cmd_accounts, "auth_configs": cmd_auth_configs,
     "connect": cmd_connect, "execute": cmd_execute}[ns.cmd](vars(ns))


if __name__ == "__main__":
    main()
