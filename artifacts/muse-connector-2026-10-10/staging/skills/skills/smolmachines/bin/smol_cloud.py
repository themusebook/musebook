#!/usr/bin/env python3
"""Smol Cloud machine control via the user-connected custom.smolmachines credential.

Subcommands:
    list                                list all machines
    create --name N [--reference alpine] [--cpus 1] [--memory-mb 256]
           [--network open|blocked] [--ttl-seconds N] [--auto-stop-seconds N]
    exec MACHINE_ID -- cmd [args...]    run a command (auto-starts a stopped machine)
    exec MACHINE_ID --shell 'cmd'       run a shell string
    get MACHINE_ID                       machine record (state, ready)
    start|stop|delete MACHINE_ID
    upload MACHINE_ID LOCAL REMOTE_PATH  PUT a file into the machine
    wait MACHINE_ID [--timeout 60]       poll until ready==true
    usage [MACHINE_ID]                   usage report (per machine or account)

Auth comes from the stored connector via dynamic_credentials; never pass or
print a raw key. Reads never go through a proxy-unaware stack: urllib only.
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

BASE = os.environ.get("SMOL_CLOUD_URL", "https://api.smolmachines.com").rstrip("/")
HOSTS = ("api.smolmachines.com",)
CREDENTIAL = "custom.smolmachines"


def request(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:2000]
        except Exception:
            detail = ""
        print(f"HTTP {e.code} on {method} {path}: {detail}", file=sys.stderr)
        sys.exit(2)


def cmd_list(_):
    print(json.dumps(request("GET", "/v1/machines"), indent=2))


def cmd_create(a):
    body = {
        "name": a.name,
        "source": {"type": a.source_type, "reference": a.reference},
        "resources": {"cpus": a.cpus, "memoryMb": a.memory_mb},
    }
    if a.network:
        body["network"] = {"mode": a.network}
    if a.ttl_seconds:
        body["ttlSeconds"] = a.ttl_seconds
    if a.auto_stop_seconds:
        body["autoStopSeconds"] = a.auto_stop_seconds
    if a.ports:
        ports = []
        for spec in a.ports:
            parts = spec.split(":")
            if len(parts) == 3:
                host, guest, port = (int(x) for x in parts)
                ports.append({"port": port, "host": host, "guest": guest})
            elif len(parts) == 2:
                host, guest = (int(x) for x in parts)
                ports.append({"port": guest, "host": host, "guest": guest})
            else:
                ports.append({"port": int(parts[0])})
        body["ports"] = ports
    print(json.dumps(request("POST", "/v1/machines", body), indent=2))


def cmd_exec(a):
    body = {"command": a.command if a.command else a.shell}
    if a.env:
        body["env"] = dict(kv.split("=", 1) for kv in a.env)
    if a.workdir:
        body["cwd"] = a.workdir
    if a.timeout:
        body["timeoutSeconds"] = a.timeout
    print(json.dumps(request("POST", f"/v1/machines/{a.machine_id}/exec", body), indent=2))


def cmd_get(a):
    print(json.dumps(request("GET", f"/v1/machines/{a.machine_id}"), indent=2))


def cmd_start(a):
    print(json.dumps(request("POST", f"/v1/machines/{a.machine_id}/start"), indent=2))


def cmd_stop(a):
    print(json.dumps(request("POST", f"/v1/machines/{a.machine_id}/stop"), indent=2))


def cmd_delete(a):
    q = "?includeUsage=true" if a.settle else ""
    res = request("DELETE", f"/v1/machines/{a.machine_id}{q}")
    print(json.dumps(res, indent=2) if res else "deleted (204)")


def cmd_upload(a):
    url = f"{BASE}/v1/machines/{a.machine_id}/files/{a.remote.lstrip('/')}"
    with open(a.local, "rb") as f:
        data = f.read()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Content-Type", "application/octet-stream")
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            print(raw.decode() if raw else "uploaded")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:1000]}", file=sys.stderr)
        sys.exit(2)


def cmd_wait(a):
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        rec = request("GET", f"/v1/machines/{a.machine_id}")
        if rec and rec.get("ready") is True:
            print(json.dumps({"ready": True, "machine_id": a.machine_id}))
            return
        time.sleep(2)
    print(f"machine {a.machine_id} did not become ready within {a.timeout}s", file=sys.stderr)
    sys.exit(3)


def cmd_usage(a):
    path = f"/v1/machines/{a.machine_id}/usage" if a.machine_id else "/v1/usage"
    print(json.dumps(request("GET", path), indent=2))


def main():
    p = argparse.ArgumentParser(prog="smol_cloud.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list"); s.set_defaults(fn=cmd_list)

    s = sub.add_parser("create")
    s.add_argument("--name", required=True)
    s.add_argument("--source-type", default="image")
    s.add_argument("--reference", default="alpine")
    s.add_argument("--cpus", type=int, default=1)
    s.add_argument("--memory-mb", type=int, default=256)
    s.add_argument("--network", choices=["open", "blocked"], default="open")
    s.add_argument("--ttl-seconds", type=int)
    s.add_argument("--auto-stop-seconds", type=int)
    s.add_argument("--ports", nargs="*")
    s.set_defaults(fn=cmd_create)

    s = sub.add_parser("exec")
    s.add_argument("machine_id")
    s.add_argument("--shell")
    s.add_argument("--env", nargs="*")
    s.add_argument("--workdir")
    s.add_argument("--timeout", type=int)
    s.add_argument("command", nargs="*")
    s.set_defaults(fn=cmd_exec)

    s = sub.add_parser("get"); s.add_argument("machine_id"); s.set_defaults(fn=cmd_get)
    s = sub.add_parser("start"); s.add_argument("machine_id"); s.set_defaults(fn=cmd_start)
    s = sub.add_parser("stop"); s.add_argument("machine_id"); s.set_defaults(fn=cmd_stop)
    s = sub.add_parser("delete"); s.add_argument("machine_id")
    s.add_argument("--settle", action="store_true",
                   help="include settled usage/cost in the delete response")
    s.set_defaults(fn=cmd_delete)

    s = sub.add_parser("upload")
    s.add_argument("machine_id"); s.add_argument("local"); s.add_argument("remote")
    s.set_defaults(fn=cmd_upload)

    s = sub.add_parser("wait")
    s.add_argument("machine_id"); s.add_argument("--timeout", type=int, default=60)
    s.set_defaults(fn=cmd_wait)

    s = sub.add_parser("usage")
    s.add_argument("machine_id", nargs="?")
    s.set_defaults(fn=cmd_usage)

    a = p.parse_args()
    if a.cmd == "exec" and not a.shell and not a.command:
        p.error("exec needs --shell 'cmd' or a command after --")
    a.fn(a)


if __name__ == "__main__":
    main()
