#!/usr/bin/env python3
"""Upstash Box control CLI. Stdlib only.

Auth: stored `custom.upstash` connector credential via surrogate on the
urllib path (X-Box-Api-Key header, only to us-east-1.box.upstash.com).
Never prints or persists secrets.

Endpoints (verified against upstash-box 1.x SDK source):
  GET    /v2/box                        list boxes
  POST   /v2/box                        create box
  GET    /v2/box/{id}/status            box status
  POST   /v2/box/{id}/pause|resume       pause / resume (keep_alive boxes never idle-pause)
  DELETE /v2/box/{id}                    delete (irreversible)
  POST   /v2/box/{id}/exec               run shell: {"command": ["sh","-c","..."]}
  GET    /v2/box/{id}/logs?limit=&offset=
  GET    /v2/box/{id}/schedules          cron schedules
  GET    /v2/box/{id}/snapshots
  POST   /v2/box/{id}/snapshots {"name": ...}
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

HOST = "us-east-1.box.upstash.com"
BASE = f"https://{HOST}"
CRED = "custom.upstash"


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    add_surrogate_to_request(req, CRED, allowed_hosts=[HOST])
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        raise RuntimeError(f"Box API {method} {path} -> HTTP {e.code}: {detail}")
    return read_json_response(resp)


def out(obj):
    print(json.dumps(obj, indent=1, default=str))


def cmd_list(args):
    q = f"?label={args.label}" if args.label else ""
    out(api("GET", f"/v2/box{q}"))


def cmd_status(args):
    out(api("GET", f"/v2/box/{args.id}/status"))


def cmd_exec(args):
    cmd = " ".join(args.command)
    r = api("POST", f"/v2/box/{args.id}/exec", {"command": ["sh", "-c", cmd]})
    print(f"exit={r.get('exit_code')}")
    if r.get("output"):
        print(r["output"])
    if r.get("error"):
        print("STDERR:", r["error"], file=sys.stderr)


def cmd_logs(args):
    out(api("GET", f"/v2/box/{args.id}/logs?limit={args.limit}&offset={args.offset}"))


def cmd_schedules(args):
    out(api("GET", f"/v2/box/{args.id}/schedules"))


def cmd_snapshots(args):
    out(api("GET", f"/v2/box/{args.id}/snapshots"))


def cmd_snapshot(args):
    out(api("POST", f"/v2/box/{args.id}/snapshots", {"name": args.name}))


def cmd_create(args):
    body = {"runtime": args.runtime}
    if args.name:
        body["name"] = args.name
    if args.size:
        body["size"] = args.size
    if args.keep_alive:
        body["keep_alive"] = True
    if args.browser:
        body["browser"] = True
    if args.labels:
        body["labels"] = args.labels.split(",")
    if args.env:
        body["env_vars"] = dict(kv.split("=", 1) for kv in args.env)
    out(api("POST", "/v2/box", body))


def cmd_delete(args):
    api("DELETE", f"/v2/box/{args.id}")
    print(f"deleted {args.id}")


def cmd_pause(args):
    api("POST", f"/v2/box/{args.id}/pause")
    print(f"paused {args.id}")


def cmd_resume(args):
    api("POST", f"/v2/box/{args.id}/resume")
    print(f"resumed {args.id}")


def main():
    p = argparse.ArgumentParser(description="Upstash Box control CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list"); s.add_argument("--label"); s.set_defaults(f=cmd_list)
    s = sub.add_parser("status"); s.add_argument("id"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("exec"); s.add_argument("id"); s.add_argument("command", nargs=argparse.REMAINDER); s.set_defaults(f=cmd_exec)
    s = sub.add_parser("logs"); s.add_argument("id"); s.add_argument("--limit", type=int, default=50); s.add_argument("--offset", type=int, default=0); s.set_defaults(f=cmd_logs)
    s = sub.add_parser("schedules"); s.add_argument("id"); s.set_defaults(f=cmd_schedules)
    s = sub.add_parser("snapshots"); s.add_argument("id"); s.set_defaults(f=cmd_snapshots)
    s = sub.add_parser("snapshot"); s.add_argument("id"); s.add_argument("--name", required=True); s.set_defaults(f=cmd_snapshot)
    s = sub.add_parser("create")
    s.add_argument("--runtime", required=True, choices=["node", "python", "golang", "ruby", "rust", "node-alpine", "python-alpine", "golang-alpine", "ruby-alpine", "rust-alpine"])
    s.add_argument("--name"); s.add_argument("--size", choices=["small", "medium", "large"])
    s.add_argument("--keep-alive", action="store_true"); s.add_argument("--browser", action="store_true")
    s.add_argument("--labels"); s.add_argument("--env", action="append")
    s.set_defaults(f=cmd_create)
    s = sub.add_parser("delete"); s.add_argument("id"); s.set_defaults(f=cmd_delete)
    s = sub.add_parser("pause"); s.add_argument("id"); s.set_defaults(f=cmd_pause)
    s = sub.add_parser("resume"); s.add_argument("id"); s.set_defaults(f=cmd_resume)

    args = p.parse_args()
    try:
        args.f(args)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
