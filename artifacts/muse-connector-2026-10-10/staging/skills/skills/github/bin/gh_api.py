#!/usr/bin/env python3
"""Surrogate-authenticated GitHub REST API caller.

Usage: gh_api.py METHOD /path [payload.json]
Reads payload from a JSON file arg or stdin. Prints response JSON.
Auth: custom.github credential via authd surrogate exchange (never reads the token).
"""
import json, sys, urllib.request
sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

BASE = "https://api.github.com"

def main():
    if len(sys.argv) < 3:
        sys.exit("usage: gh_api.py METHOD /path [payload.json|-]")
    method, path = sys.argv[1], sys.argv[2]
    payload = None
    if len(sys.argv) > 3:
        raw = sys.stdin.read() if sys.argv[3] == "-" else open(sys.argv[3]).read()
        payload = json.loads(raw)
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    add_surrogate_to_request(req, "custom.github", allowed_hosts=["api.github.com"])
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(payload).encode()
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        sys.exit(f"GitHub API {method} {path} -> HTTP {e.code}: {detail}")
    print(json.dumps(read_json_response(resp), indent=2))

if __name__ == "__main__":
    main()
