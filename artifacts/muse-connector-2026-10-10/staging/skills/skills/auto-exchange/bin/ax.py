#!/usr/bin/env python3
"""auto.exchange API CLI. Auth via authd surrogate (custom.auto-exchange).

Never prints or persists raw credentials; only hsurr:* surrogates are sent,
and only to api.auto.exchange.
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    ensure_allowed_url,
    read_json_response,
)

BASE = "https://api.auto.exchange"
CRED = "custom.auto-exchange"
HOSTS = ["api.auto.exchange"]


def authed_request(method, path, data=None, headers=None, content_type=None):
    url = BASE + path
    ensure_allowed_url(url, HOSTS)
    req = urllib.request.Request(url, method=method)
    if data is not None:
        req.data = data
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if content_type:
        req.add_header("Content-Type", content_type)
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    return req


def call(method, path, payload=None):
    body = None
    ctype = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        ctype = "application/json"
    req = authed_request(method, path, data=body, content_type=ctype)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return read_json_response(resp)


def cmd_account(_):
    print(json.dumps(call("GET", "/account"), indent=2))


def cmd_mine(_):
    print(json.dumps(call("GET", "/agents/mine"), indent=2))


def cmd_get(args):
    print(json.dumps(call("GET", f"/agents/by-slug/{args.slug}"), indent=2))


def cmd_create(args):
    with open(args.json) as f:
        payload = json.load(f)
    print(json.dumps(call("POST", "/agents", payload), indent=2))


def cmd_patch(args):
    with open(args.json) as f:
        payload = json.load(f)
    print(json.dumps(call("PATCH", f"/agents/{args.id}", payload), indent=2))


def cmd_run(args):
    payload = {"prompt": args.prompt}
    if args.session:
        payload["session_id"] = args.session
    if args.stateless:
        payload["stateless"] = True
    print(json.dumps(call("POST", f"/agents/{args.id}/run", payload), indent=2))


def encode_multipart(path):
    boundary = uuid.uuid4().hex
    filename = os.path.basename(path)
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        file_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def cmd_upload(args):
    body, ctype = encode_multipart(args.file)
    req = authed_request("POST", "/uploads", data=body, content_type=ctype)
    with urllib.request.urlopen(req, timeout=120) as resp:
        print(json.dumps(read_json_response(resp), indent=2))


def main():
    p = argparse.ArgumentParser(description="auto.exchange API CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("account", help="GET /account")
    sub.add_parser("mine", help="GET /agents/mine")

    g = sub.add_parser("get", help="GET /agents/by-slug/:slug")
    g.add_argument("--slug", required=True)

    c = sub.add_parser("create", help="POST /agents")
    c.add_argument("--json", required=True, help="Path to JSON payload file")

    pt = sub.add_parser("patch", help="PATCH /agents/:id")
    pt.add_argument("--id", required=True)
    pt.add_argument("--json", required=True, help="Path to JSON patch file")

    r = sub.add_parser("run", help="POST /agents/:id/run")
    r.add_argument("--id", required=True)
    r.add_argument("--prompt", required=True)
    r.add_argument("--session", default=None)
    r.add_argument("--stateless", action="store_true")

    u = sub.add_parser("upload", help="POST /uploads (multipart file)")
    u.add_argument("--file", required=True)

    args = p.parse_args()
    try:
        {
            "account": cmd_account,
            "mine": cmd_mine,
            "get": cmd_get,
            "create": cmd_create,
            "patch": cmd_patch,
            "run": cmd_run,
            "upload": cmd_upload,
        }[args.cmd](args)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
