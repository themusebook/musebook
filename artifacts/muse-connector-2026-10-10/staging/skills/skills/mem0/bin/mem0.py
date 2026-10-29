#!/usr/bin/env python3
"""Mem0 persistent memory CLI via the stored custom.mem0 connector.

The raw API key never touches this process: requests carry an hsurr:*
surrogate and Sentinel/authd swaps in the real credential on the way out.
Never prints or persists the key.

Usage:
    mem0.py search <user_id> <query> [--top-k 5]
    mem0.py add <user_id> "<user message>" ["<assistant message>"] [--meta k=v ...]
    mem0.py get <user_id> [--limit 20]
    mem0.py delete <user_id> <memory_id>
    mem0.py clear <user_id>            # delete ALL memories for this user
    mem0.py ping                       # verify auth works

Auth placement comes from the custom.mem0 connector (bearer_header on
api.mem0.ai). mem0's add endpoint processes asynchronously — a freshly added
memory may take a few seconds to appear in search results.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
import dynamic_credentials as dc  # noqa: E402

BASE = "https://api.mem0.ai"
ALLOWED = ("api.mem0.ai",)
CREDENTIAL = "custom.mem0"
ENTRY = "access_token"


def _auth_header():
    # mem0's platform API reads the key as `Authorization: Token <key>`; the
    # stored connector's configured placement is bearer_header, so place the
    # surrogate manually with the Token prefix.
    entry = dc.dynamic_credential_entry(CREDENTIAL, ENTRY)
    return "Token " + str(entry["surrogate"]).strip()


def _req(method, path, payload=None, params=None, auth_prefix=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if auth_prefix == "bearer":
        dc.add_surrogate_to_request(req, CREDENTIAL, entry_name=ENTRY,
                                    allowed_hosts=ALLOWED)
    else:
        dc.ensure_allowed_url(req.full_url, ALLOWED)
        req.add_header("Authorization", _auth_header())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dc.read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = "<unreadable>"
        return e.code, {"http_error": e.code, "body": body}


def cmd_search(args):
    status, out = _req("POST", "/v1/memories/search/",
                       {"query": args.query, "user_id": args.user_id,
                        "top_k": args.top_k})
    return _report(status, out, pick=lambda o: o.get("results") or o)


def cmd_add(args):
    messages = [{"role": "user", "content": args.user_msg}]
    if args.assistant_msg:
        messages.append({"role": "assistant", "content": args.assistant_msg})
    payload = {"messages": messages, "user_id": args.user_id,
               "metadata": dict(kv.split("=", 1) for kv in args.meta)}
    status, out = _req("POST", "/v1/memories/", payload)
    return _report(status, out)


def cmd_get(args):
    status, out = _req("GET", "/v1/memories/",
                       params={"user_id": args.user_id})
    return _report(status, out, pick=lambda o: o.get("results") or o)


def cmd_delete(args):
    status, out = _req("DELETE", f"/v1/memories/{args.memory_id}",
                       params={"user_id": args.user_id})
    return _report(status, out)


def cmd_clear(args):
    status, out = _req("DELETE", "/v1/memories/",
                       params={"user_id": args.user_id})
    return _report(status, out)


def cmd_ping(args):
    status, out = _req("GET", "/v1/memories/",
                       params={"user_id": "__mem0_cli_ping__"})
    if status == 401:
        print("PING FAILED: auth rejected (401)", file=sys.stderr)
        return 1
    print(f"ping ok (status {status})")
    return 0


def _report(status, out, pick=None):
    ok = 200 <= status < 300
    item = pick(out) if pick else out
    print(json.dumps(item, indent=2, ensure_ascii=False)[:4000])
    if not ok:
        print(f"request failed with HTTP {status}", file=sys.stderr)
        return 1
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search"); p.add_argument("user_id"); p.add_argument("query")
    p.add_argument("--top-k", type=int, default=5); p.set_defaults(fn=cmd_search)

    p = sub.add_parser("add"); p.add_argument("user_id"); p.add_argument("user_msg")
    p.add_argument("assistant_msg", nargs="?", default=None)
    p.add_argument("--meta", action="append", default=[]); p.set_defaults(fn=cmd_add)

    p = sub.add_parser("get"); p.add_argument("user_id")
    p.add_argument("--limit", type=int, default=20); p.set_defaults(fn=cmd_get)

    p = sub.add_parser("delete"); p.add_argument("user_id"); p.add_argument("memory_id")
    p.set_defaults(fn=cmd_delete)

    p = sub.add_parser("clear"); p.add_argument("user_id"); p.set_defaults(fn=cmd_clear)
    p = sub.add_parser("ping"); p.set_defaults(fn=cmd_ping)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
