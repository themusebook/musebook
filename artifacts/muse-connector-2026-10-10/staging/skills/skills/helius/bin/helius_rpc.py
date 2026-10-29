#!/usr/bin/env python3
"""Call Helius Solana JSON-RPC with the stored custom.helius credential.

The API key is attached as a surrogate query parameter by authd; this script
never sees the raw key. Authenticated requests are restricted to the Helius
RPC hosts in ALLOWED.

Usage:
    helius_rpc.py --network devnet --method getBalance --params '["<address>"]'
    helius_rpc.py --network devnet --method getAccountInfo --params '["<address>", {"encoding": "jsonParsed"}]'
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    read_json_response,
    url_with_surrogate_query_param,
)

HOSTS = {
    "devnet": "https://devnet.helius-rpc.com/",
    "mainnet": "https://mainnet.helius-rpc.com/",
}
ALLOWED = ["devnet.helius-rpc.com", "mainnet.helius-rpc.com"]
CREDENTIAL = "custom.helius"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", choices=sorted(HOSTS), default="devnet")
    ap.add_argument("--method", required=True, help="JSON-RPC method, e.g. getBalance")
    ap.add_argument("--params", default="[]", help="JSON array of params")
    args = ap.parse_args()

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError:
        sys.exit("error: --params must be valid JSON")

    try:
        url = url_with_surrogate_query_param(
            HOSTS[args.network], CREDENTIAL, allowed_hosts=ALLOWED
        )
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")

    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": args.method, "params": params}
    ).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = read_json_response(resp)
    except DynamicCredentialError as exc:
        sys.exit(f"request error: {exc}")
    except Exception as exc:  # noqa: BLE001 - surface provider/network errors plainly
        sys.exit(f"rpc error: {exc}")

    print(json.dumps(out))


if __name__ == "__main__":
    main()
