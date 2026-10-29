#!/usr/bin/env python3
"""Create a Hugging Face Hub repo and upload files to it.

Auth: stored `custom.huggingface` connector via the dynamic-credential
surrogate (never a raw token in chat, env files, or logs).

Usage:
    hf_publish.py --whoami
    hf_publish.py --repo NAME [--type dataset|model|space] [--private]
                  --upload LOCAL:REMOTE [--upload ...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry  # noqa: E402

API = "https://huggingface.co/api"
REPO_PATHS = {"model": "models", "dataset": "datasets", "space": "spaces"}


class HFError(Exception):
    pass


def api_token() -> str:
    entry = dynamic_credential_entry("custom.huggingface")
    tok = str(entry["surrogate"]).strip()
    if not tok.startswith("hsurr:"):
        raise HFError("credential did not resolve to a surrogate")
    return tok


def req_json(method: str, url: str, token: str, payload=None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        raise HFError(f"{method} {url} -> HTTP {e.code}: {body}")


def whoami(token: str) -> dict:
    return req_json("GET", f"{API}/whoami-v2", token)


def create_repo(token: str, name: str, repo_type: str, private: bool) -> dict:
    return req_json("POST", f"{API}/repos/create", token, {
        "name": name,
        "type": repo_type,
        "private": private,
    })


def commit_files(token: str, namespace: str, repo: str, repo_type: str,
               files: list[tuple[str, str]]) -> dict:
    """Single-commit upload using the NDJSON commit endpoint
    (Content-Type: application/x-ndjson), as huggingface_hub does."""
    import base64
    lines = [json.dumps({
        "key": "header",
        "value": {
            "summary": "Upload whitepaper v0.2 + README",
            "description": "Clawd Agentic Layer whitepaper v0.2 (20 pages) and repo README.",
        },
    })]
    for local, remote in files:
        with open(local, "rb") as f:
            content = f.read()
        lines.append(json.dumps({
            "key": "file",
            "value": {
                "content": base64.b64encode(content).decode(),
                "path": remote,
                "encoding": "base64",
            },
        }))
    body = ("\n".join(lines) + "\n").encode()
    repo_id = f"{namespace}/{repo}"
    url = f"{API}/{repo_type}s/{repo_id}/commit/main"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-ndjson",
    })
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body_e = e.read().decode(errors="replace")[:500]
        raise HFError(f"POST {url} -> HTTP {e.code}: {body_e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--whoami", action="store_true")
    ap.add_argument("--repo", default="")
    ap.add_argument("--type", choices=["dataset", "model", "space"], default="dataset")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--upload", action="append", default=[],
                    help="LOCAL:REMOTE, repeatable")
    args = ap.parse_args()

    token = api_token()
    me = whoami(token)
    namespace = me.get("name")
    if args.whoami:
        print(namespace)
        return 0

    if not args.repo:
        print("ERROR: --repo is required", file=sys.stderr)
        return 1
    if not args.upload:
        print("ERROR: at least one --upload LOCAL:REMOTE is required", file=sys.stderr)
        return 1

    try:
        create_repo(token, args.repo, args.type, args.private)
        print(f"[hf] repo created: {namespace}/{args.repo} ({args.type}, "
              f"{'private' if args.private else 'public'})")
    except HFError as e:
        # 409 = already exists; treat as fine and continue uploading.
        if "409" in str(e):
            print(f"[hf] repo {namespace}/{args.repo} already exists; uploading into it")
        else:
            print(f"[hf] CREATE FAILED: {e}", file=sys.stderr)
            return 1

    files: list[tuple[str, str]] = []
    for spec in args.upload:
        if ":" not in spec:
            print(f"ERROR: bad --upload spec (need LOCAL:REMOTE): {spec}", file=sys.stderr)
            return 1
        local, remote = spec.rsplit(":", 1)
        if not os.path.isfile(local):
            print(f"ERROR: local file not found: {local}", file=sys.stderr)
            return 1
        files.append((local, remote))
    try:
        commit_files(token, namespace, args.repo, args.type, files)
        for local, remote in files:
            print(f"[hf] uploaded {local} -> {remote} "
                  f"({os.path.getsize(local)} bytes)")
    except HFError as e:
        print(f"[hf] UPLOAD FAILED: {e}", file=sys.stderr)
        return 1

    base = {"model": "https://huggingface.co",
            "dataset": "https://huggingface.co/datasets",
            "space": "https://huggingface.co/spaces"}[args.type]
    print(f"[hf] URL: {base}/{namespace}/{args.repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
