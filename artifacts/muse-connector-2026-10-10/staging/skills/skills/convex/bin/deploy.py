#!/usr/bin/env python3
"""Deploy a Convex project using the stored custom.convex credential.

The Convex CLI parses CONVEX_DEPLOY_KEY locally (it requires a `|` in the
value), so a raw surrogate can't go through the env var. Instead this script
passes the surrogate via the hidden `--admin-key` flag together with `--url`:
that path skips deploy-key format parsing entirely and the CLI sends
`Authorization: Convex <surrogate>`, which authd swaps for the real deploy key
on egress.

Usage:
    deploy.py [--project-dir DIR] [--url URL] [-- extra convex args...]

Defaults: project dir ~/workspace/musebook/convex,
          url https://enchanted-egret-184.convex.cloud
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    dynamic_credential_entry,
    ensure_allowed_url,
)

ALLOWED_HOSTS = [
    "api.convex.dev",
    "enchanted-egret-184.convex.cloud",
    "veracious-snake-356.convex.cloud",  # user-supplied 2026-09-18
]
DEFAULT_PROJECT_DIR = os.path.expanduser("~/workspace/musebook/convex")
DEFAULT_URL = "https://enchanted-egret-184.convex.cloud"


def main(argv: list[str]) -> int:
    project_dir = DEFAULT_PROJECT_DIR
    url = DEFAULT_URL
    extra: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--project-dir" and i + 1 < len(argv):
            project_dir = argv[i + 1]
            i += 2
        elif argv[i] == "--url" and i + 1 < len(argv):
            url = argv[i + 1]
            i += 2
        elif argv[i] == "--":
            extra.extend(argv[i + 1 :])
            break
        else:
            extra.append(argv[i])
            i += 1

    ensure_allowed_url(url, ALLOWED_HOSTS)
    entry = dynamic_credential_entry("custom.convex")
    surrogate = str(entry["surrogate"]).strip()
    if not surrogate.startswith("hsurr:"):
        print("error: credential did not return a surrogate", file=sys.stderr)
        return 1

    # Prefer the project's local convex binary: `npx --yes convex` downloads a
    # fresh copy into the npx cache, bypassing the surrogate-auth patch applied
    # to the local node_modules (see note below).
    local_bin = os.path.join(project_dir, "node_modules", ".bin", "convex")
    if os.path.isfile(local_bin):
        convex_cmd = [local_bin]
    else:
        convex_cmd = ["npx", "--yes", "convex"]
    cmd = [
        *convex_cmd,
        "deploy",
        "--url",
        url,
        "--admin-key",
        surrogate,
        "--yes",
        "--skip-workos-check",
        *extra,
    ]
    print(f"+ {' '.join(cmd[:6])} --admin-key <surrogate> {' '.join(cmd[8:])}")
    print(f"  project dir: {project_dir}", flush=True)
    proc = subprocess.run(cmd, cwd=project_dir)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
