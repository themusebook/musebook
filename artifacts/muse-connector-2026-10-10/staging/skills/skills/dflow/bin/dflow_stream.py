#!/usr/bin/env python3
"""Live DFlow quote stream (read-only).

Usage: dflow_stream.py <baseMint> <quoteMint> [--seconds N] [--dev]

--dev uses the keyless dev endpoint (rate-limited). Default is production
wss://quote-api.dflow.net/quote-stream with the connector credential.
The API key is never exposed: the node client receives only the
proxy-resolved surrogate via argv.
"""
import os
import subprocess
import sys

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
sys.path.insert(0, "/home/hatch/workspace/skills/dflow/bin")
import dynamic_credentials as dc
import dflow_client as C

SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

BIN = "/home/hatch/workspace/skills/dflow/bin/dflow_stream.mjs"


def main():
    args = []
    skip_next = False
    for a in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in ("--seconds",):
            skip_next = True
            continue
        if a.startswith("--"):
            continue
        args.append(a)
    dev = "--dev" in sys.argv
    seconds = "15"
    for i, a in enumerate(sys.argv):
        if a == "--seconds" and i + 1 < len(sys.argv):
            seconds = sys.argv[i + 1]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    base_mint, quote_mint = args
    if dev:
        url, surrogate = "wss://dev-quote-api.dflow.net/quote-stream", None
    else:
        url = "wss://quote-api.dflow.net/quote-stream"
        entry = dc.dynamic_credential_entry(C.CRED, "access_token")
        dc.ensure_allowed_url("https://quote-api.dflow.net/", C.ALLOWED)
        surrogate = str(entry["surrogate"]).strip()
    cmd = ["node", BIN, "--url", url, "--base", base_mint, "--quote", quote_mint,
           "--seconds", seconds]
    if surrogate:
        cmd += ["--surrogate", surrogate]
    env = dict(os.environ)
    # never let the surrogate leak into logs: it only travels in argv
    p = subprocess.run(cmd, env=env)
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
