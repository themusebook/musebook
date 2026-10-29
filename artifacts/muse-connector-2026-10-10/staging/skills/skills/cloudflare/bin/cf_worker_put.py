#!/usr/bin/env python3
"""Upload a single-module Worker via the Cloudflare script API (multipart PUT).

Unlike cf_worker_deploy.py (which is hardcoded to musebook-proxy via wrangler),
this deploys ANY single-file worker with explicit bindings metadata. Existing
secrets on the worker are preserved across script uploads; bindings in
--metadata-json REPLACE the script configuration, so include everything.

Usage:
  cf_worker_put.py --name NAME --file worker.js [--account ID]
                   [--metadata-json '{"bindings":[...]}']

Example bindings metadata:
  {"main_module":"worker.js","compatibility_date":"2025-01-01","bindings":[
    {"type":"send_email","name":"EMAIL"},
    {"type":"plain_text","name":"OPENROUTER_MODEL","text":"nvidia/nemotron-3.5-lightning:free"}
  ]}

NOTE: script-upload ignores top-level "vars" — use plain_text bindings instead.
"""
import argparse
import io
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry, DynamicCredentialError

BASE = "https://api.cloudflare.com/client/v4"
DEFAULT_ACCOUNT = "7640372571bf2d69ed5d58a6a6d8929e"


def encode_multipart(fields, files):
    # fields: [(name, value, ctype)]; files: [(part_name, filename, data, ctype)]
    boundary = "----cfworkerputboundary"
    buf = io.BytesIO()
    for name, value, ctype in fields:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n'.encode())
        buf.write(f"Content-Type: {ctype}\r\n\r\n".encode())
        buf.write(value if isinstance(value, bytes) else value.encode())
        buf.write(b"\r\n")
    for part_name, filename, data, ctype in files:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{part_name}"; filename="{filename}"\r\n'.encode())
        buf.write(f"Content-Type: {ctype}\r\n\r\n".encode())
        buf.write(data)
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue(), boundary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--account", default=DEFAULT_ACCOUNT)
    ap.add_argument("--metadata-json", default="{}")
    args = ap.parse_args()

    try:
        metadata = json.loads(args.metadata_json)
    except json.JSONDecodeError:
        sys.exit("error: --metadata-json must be valid JSON")
    if "main_module" not in metadata:
        metadata["main_module"] = args.file.split("/")[-1]

    try:
        entry = dynamic_credential_entry("custom.cloudflare", "access_token")
    except DynamicCredentialError as e:
        print(f"error: credential: {e}")
        return 1
    surrogate = str(entry["surrogate"]).strip()
    if not surrogate.startswith("hsurr:"):
        print("error: credential did not return a surrogate")
        return 1

    with open(args.file, "rb") as f:
        script = f.read()

    # NOTE: for ES modules each module is a form part named by its filename
    # (matching metadata.main_module), NOT a part named "script". The module
    # part MUST use Content-Type application/javascript+module or the API
    # parses it as a classic service-worker script.
    body, boundary = encode_multipart(
        [("metadata", json.dumps(metadata), "application/json")],
        [(args.file.split("/")[-1], args.file.split("/")[-1], script,
          "application/javascript+module")],
    )
    url = f"{BASE}/accounts/{args.account}/workers/scripts/{args.name}"
    req = urllib.request.Request(
        url, data=body, method="PUT",
        headers={
            "Authorization": f"Bearer {surrogate}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = resp.read().decode()
    except Exception as e:
        body_txt = ""
        if hasattr(e, "read"):
            try:
                body_txt = e.read().decode()[:2000]
            except Exception:
                pass
        print(f"error: upload failed: {e}\n{body_txt}")
        return 1
    print(out[:3000].replace(surrogate, "[REDACTED]"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
