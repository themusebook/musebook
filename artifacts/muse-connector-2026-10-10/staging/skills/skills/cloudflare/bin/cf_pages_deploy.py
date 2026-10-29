#!/usr/bin/env python3
"""Deploy ~/workspace/musebook/web to Cloudflare Pages via wrangler.

Gets only the hsurr:* surrogate for custom.cloudflare via
dynamic_credentials.py and passes it transiently as CLOUDFLARE_API_TOKEN
to wrangler. The surrogate is never printed or persisted; any accidental
echo in wrangler output is scrubbed before display.
"""
import os
import subprocess
import sys

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry, DynamicCredentialError

WEB_DIR = "/home/hatch/workspace/musebook/web"
PROJECT = "musebook"
BRANCH = "main"


def main() -> int:
    try:
        entry = dynamic_credential_entry("custom.cloudflare", "access_token")
    except DynamicCredentialError as e:
        print(f"error: credential: {e}")
        return 1
    surrogate = str(entry["surrogate"]).strip()
    if not surrogate.startswith("hsurr:"):
        print("error: credential did not return a surrogate")
        return 1

    env = dict(os.environ)
    env["CLOUDFLARE_API_TOKEN"] = surrogate
    env["CI"] = "1"
    env["WRANGLER_SEND_METRICS"] = "false"

    proc = subprocess.run(
        ["npx", "-y", "wrangler", "pages", "deploy", WEB_DIR,
         "--project-name", PROJECT, "--branch", BRANCH],
        env=env, capture_output=True, text=True, timeout=900,
    )
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    # Belt and braces: never let the surrogate reach the terminal or logs.
    safe = out.replace(surrogate, "[REDACTED]")
    print(safe)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
