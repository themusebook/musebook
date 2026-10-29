#!/usr/bin/env python3
"""Pinata pinning CLI.

Auth: tries the stored `custom.pinata` connector surrogate first (Bearer on
api.pinata.cloud). If the surrogate is missing or Pinata rejects it (401/403),
falls back to the PINATA_JWT environment variable (user-supplied, transient;
never written to disk). The raw token is never printed or logged.

Subcommands:
  test-auth            GET /data/testAuthentication
  pin-json   --name N --file F.json [--key K]
                       POST /pinning/pinJSONToIPFS  (wraps file content)
  pin-file   --name N --file F
                       POST /pinning/pinFileToIPFS  (multipart)
  unpin      --cid CID
                       DELETE /pinning/unpin/CID
  pin-list   [--limit N]
                       GET /pinning/pinList?status=pinned
"""
from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    add_surrogate_to_request,
    read_json_response,
)

API = "https://api.pinata.cloud"
ALLOWED = ("api.pinata.cloud",)
UA = "clawd-pinata/1.0"


def _bearer_from_env() -> str | None:
    tok = os.environ.get("PINATA_JWT", "").strip()
    return tok or None


def _request(method: str, path: str, data: bytes | None = None,
             content_type: str | None = None) -> urllib.request.Request:
    headers = {"User-Agent": UA}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers=headers)
    try:
        add_surrogate_to_request(req, "custom.pinata", allowed_hosts=ALLOWED)
        return req
    except DynamicCredentialError:
        tok = _bearer_from_env()
        if not tok:
            raise
        req.add_header("Authorization", "Bearer " + tok)
        return req


def _call(method: str, path: str, data: bytes | None = None,
          content_type: str | None = None) -> dict:
    """One call; on 401/403 retry once with the env JWT if the surrogate failed."""
    def attempt(req: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return {"http": resp.status, "body": read_json_response(resp)}
        except urllib.error.HTTPError as e:
            raw = e.read()[:500].decode("utf-8", "replace")
            return {"http": e.code, "error": raw}

    req = _request(method, path, data, content_type)
    out = attempt(req)
    if out.get("http") in (401, 403) and req.get_header("Authorization", "").startswith("Bearer hsurr"):
        # Surrogate was attached but rejected -> retry with env JWT once.
        tok = _bearer_from_env()
        if tok:
            headers = {"User-Agent": UA, "Authorization": "Bearer " + tok}
            if content_type:
                headers["Content-Type"] = content_type
            out = attempt(urllib.request.Request(API + path, data=data,
                                                method=method, headers=headers))
    return out


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """fields: name->str ; files: name->(filename, bytes, content_type)."""
    boundary = "----clawd" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, value in fields.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(f"{value}\r\n".encode())
    for name, (filename, data, ctype) in files.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        buf.write(f"Content-Type: {ctype}\r\n\r\n".encode())
        buf.write(data)
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def cmd_test_auth(_args: argparse.Namespace) -> int:
    print(json.dumps(_call("GET", "/data/testAuthentication"), indent=2))
    return 0


def cmd_pin_json(args: argparse.Namespace) -> int:
    with open(args.file, "rb") as f:
        content = json.load(f)
    payload: dict = {"pinataContent": content}
    if args.name or args.key:
        payload["pinataMetadata"] = {"name": args.name or args.file}
        if args.key:
            payload["pinataMetadata"]["keyvalues"] = {"key": args.key}
    body = json.dumps(payload).encode()
    print(json.dumps(_call("POST", "/pinning/pinJSONToIPFS", body,
                           "application/json"), indent=2))
    return 0


def cmd_pin_file(args: argparse.Namespace) -> int:
    with open(args.file, "rb") as f:
        data = f.read()
    ctype = mimetypes.guess_type(args.file)[0] or "application/octet-stream"
    metadata = json.dumps({"name": args.name or os.path.basename(args.file)})
    body, ctype_hdr = _multipart(
        {"pinataMetadata": metadata},
        {"file": (os.path.basename(args.file), data, ctype)},
    )
    print(json.dumps(_call("POST", "/pinning/pinFileToIPFS", body, ctype_hdr),
                     indent=2))
    return 0


def cmd_unpin(args: argparse.Namespace) -> int:
    print(json.dumps(_call("DELETE", "/pinning/unpin/" + args.cid), indent=2))
    return 0


def cmd_pin_list(args: argparse.Namespace) -> int:
    path = f"/data/pinList?status=pinned&pageLimit={args.limit}"
    print(json.dumps(_call("GET", path), indent=2)[:4000])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pinata pinning CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("test-auth")

    p = sub.add_parser("pin-json")
    p.add_argument("--file", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--key", default=None)

    p = sub.add_parser("pin-file")
    p.add_argument("--file", required=True)
    p.add_argument("--name", default=None)

    p = sub.add_parser("unpin")
    p.add_argument("--cid", required=True)

    p = sub.add_parser("pin-list")
    p.add_argument("--limit", type=int, default=10)

    args = ap.parse_args()
    return {
        "test-auth": cmd_test_auth,
        "pin-json": cmd_pin_json,
        "pin-file": cmd_pin_file,
        "unpin": cmd_unpin,
        "pin-list": cmd_pin_list,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
