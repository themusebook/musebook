#!/usr/bin/env python3
"""Put a Cloudflare Workers secret from a file, using the stored custom.cloudflare
credential via surrogate (same pattern as cf_worker_deploy.py). Never prints or
persists the secret value."""
import os, subprocess, sys

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import dynamic_credential_entry, DynamicCredentialError

WORKER_DIR = os.path.expanduser("~/workspace/musebook/cloudflare")

def main():
    if len(sys.argv) not in (3, 4):
        print("usage: cf_secret_put.py SECRET_NAME FILE [WORKER_DIR]", file=sys.stderr)
        sys.exit(2)
    name, path = sys.argv[1], sys.argv[2]
    workdir = sys.argv[3] if len(sys.argv) == 4 else WORKER_DIR
    try:
        entry = dynamic_credential_entry("custom.cloudflare", "access_token")
    except DynamicCredentialError as e:
        print(f"error: credential: {e}")
        sys.exit(1)
    surrogate = str(entry["surrogate"]).strip()
    if not surrogate.startswith("hsurr:"):
        print("error: credential did not return a surrogate")
        sys.exit(1)
    env = dict(os.environ)
    env["CLOUDFLARE_API_TOKEN"] = surrogate
    with open(path, "rb") as f:
        secret = f.read()
    proc = subprocess.run(
        ["npx", "-y", "wrangler", "secret", "put", name],
        input=secret, env=env, capture_output=True, timeout=300,
        cwd=workdir,
    )
    out = (proc.stdout.decode() + proc.stderr.decode()).replace(surrogate, "[REDACTED]")
    print(out[-1500:])
    sys.exit(proc.returncode)

main()
