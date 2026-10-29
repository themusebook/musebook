#!/usr/bin/env python3
"""Solana Tracker Datastream CLI.

Builds the authenticated WebSocket URL (credential stays in the vault;
only an hsurr: surrogate travels in the URL, swapped for the real key by
the egress proxy) and execs the Node listener.

Usage:
  ds.py [--seconds N] [--limit N] [--rooms latest,graduating]
        [--token MINT] [--raw]

Examples:
  ds.py --seconds 30                        # latest launches for 30s
  ds.py --seconds 60 --rooms latest,graduating --limit 20
  ds.py --seconds 60 --token <mint>          # price+volume rooms for a token
"""
import os
import sys

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    url_with_surrogate_path_segment,
    DynamicCredentialError,
)

HERE = os.path.dirname(os.path.abspath(__file__))
CRED = "custom.solana-tracker-datastream"
ALLOWED = ["datastream.solanatracker.io"]


def main() -> int:
    try:
        url = url_with_surrogate_path_segment(
            "wss://datastream.solanatracker.io/{}/",
            CRED,
            allowed_hosts=ALLOWED,
        )
    except DynamicCredentialError as e:
        print(f"[datastream] credential: {e}", file=sys.stderr)
        return 1
    env = dict(os.environ, DATASTREAM_WS_URL=url)
    node = os.path.join(HERE, "ds_listen.mjs")
    os.execvpe("node", ["node", node] + sys.argv[1:], env)


if __name__ == "__main__":
    sys.exit(main())
