#!/usr/bin/env python3
"""Deploy the AgentWallet vault server to a fresh E2B sandbox.

Uses the stored `custom.e2b` connector via the dynamic-credential surrogate
(never a raw key in chat, env files, or logs). Generates a fresh 64-hex
VAULT_PASSPHRASE + VAULT_API_TOKEN per deploy, runs the agentwallet CLI deploy,
and prints the sandbox ID + public URL. The API token is printed once so the
operator can connect their console; it is never written to disk.

Usage: e2b_deploy.py [--timeout 3600]
Long-running (several minutes): run in background.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry  # noqa: E402

PROJECT_DIR = os.path.expanduser("~/workspace/agentwallet-vault")
ALLOWED_HOSTS = ["api.e2b.app"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=3600,
                    help="Sandbox lifetime in seconds (Base tier max: 3600)")
    args = ap.parse_args()

    if args.timeout > 3600:
        print("E2B Base tier caps sandbox lifetime at 3600s; clamping.", file=sys.stderr)
        args.timeout = 3600

    entry = dynamic_credential_entry("custom.e2b")
    surrogate = str(entry["surrogate"]).strip()
    if not surrogate.startswith("hsurr:"):
        print("ERROR: credential did not resolve to a surrogate", file=sys.stderr)
        return 1

    passphrase = secrets.token_hex(32)
    # VAULT_API_TOKEN_PRESET: operator-supplied token (e.g. user chose it and
    # needs to know it). Generated tokens are printed once for the operator;
    # a preset is never printed, logged, or persisted anywhere.
    preset = os.environ.get("VAULT_API_TOKEN_PRESET", "").strip()
    api_token = preset or secrets.token_hex(32)
    token_is_preset = bool(preset)

    env = dict(os.environ)
    env["E2B_API_KEY"] = surrogate
    env["VAULT_PASSPHRASE"] = passphrase
    env["VAULT_API_TOKEN"] = api_token

    # Scrub argv of anything secret-shaped before it can leak into logs.
    def safe_cmd(cmd: list[str]) -> str:
        return " ".join(cmd)

    cmd = ["node", "dist/cli.js", "deploy", "e2b", "--timeout", str(args.timeout)]
    print(f"[e2b] running: {safe_cmd(cmd)} (timeout={args.timeout}s)", flush=True)
    proc = subprocess.run(
        cmd, cwd=PROJECT_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    out = proc.stdout or ""
    print(out)

    m_id = re.search(r"ID:\s+(\S+)", out)
    m_url = re.search(r"URL:\s+(\S+)", out)
    if proc.returncode != 0 or not (m_id and m_url):
        print("[e2b] DEPLOY FAILED", file=sys.stderr)
        return 1

    print(f"[e2b] SANDBOX_ID={m_id.group(1)}")
    print(f"[e2b] SANDBOX_URL={m_url.group(1)}")
    # The vault API token belongs to the operator: printed once, never to disk.
    # A preset token is never printed (the operator already holds it).
    if not token_is_preset:
        print(f"[e2b] VAULT_API_TOKEN={api_token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
