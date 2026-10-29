#!/usr/bin/env python3
"""Deploy ~/workspace/musebook/cloudflare/worker.js to the musebook-proxy Worker.

Uses the stored custom.cloudflare credential via surrogate, passed transiently
as CLOUDFLARE_API_TOKEN to wrangler. Never prints or persists the secret.
Existing secrets/bindings on the worker are preserved across script uploads.
"""
import os
import subprocess
import sys

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry, DynamicCredentialError

WORKER_JS = "/home/hatch/workspace/musebook/cloudflare/worker.js"
WORKER_DIR = "/home/hatch/workspace/musebook/cloudflare"
NAME = "musebook-proxy"


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
        ["npx", "-y", "wrangler", "deploy"],
        env=env, capture_output=True, text=True, timeout=900,
        cwd=WORKER_DIR,
    )
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    safe = out.replace(surrogate, "[REDACTED]")
    print(safe)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
