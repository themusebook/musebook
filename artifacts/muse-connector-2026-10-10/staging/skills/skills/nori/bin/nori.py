#!/usr/bin/env python3
"""Nori service-agent helper (dry-run tooling only).

Usage:
    nori.py discover --url <NORI_URL>
        Fetch /.well-known/agent-card.json and /rate-card, print a summary.
        Read-only; always the first step with a new NORI_URL.

    nori.py call chat --url <NORI_URL> --model <provider/model> --prompt "..." [--system "..."]
    nori.py call image --url <NORI_URL> --prompt "..." [--size 1024x1024]
    nori.py call rpc --url <NORI_URL> --method getBalance --params '["<address>"]'

        DRY-RUN ONLY: prints the exact curl for the call and exits.
        It never sends the request, never pays, never signs anything.
        Review the price on the rate card and get the user's explicit approval
        of the exact spend before running the printed curl yourself.

Uses urllib (respects https_proxy env) for the read-only discovery calls.
`call` performs zero network I/O by design.
"""
import argparse
import json
import shlex
import sys
import urllib.request

UA = "clawd-nori/1.0"
TIMEOUT = 20


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_discover(args):
    base = args.url.rstrip("/")
    print(f"# Nori discovery: {base}\n")
    try:
        card = get_json(base + "/.well-known/agent-card.json")
    except Exception as e:
        print(f"agent-card.json: FAILED ({e})")
        card = None
    try:
        rate = get_json(base + "/rate-card")
    except Exception as e:
        print(f"rate-card: FAILED ({e})")
        rate = None

    if card:
        print("## agent card")
        for key in ("name", "description", "version", "serviceExecutiveAddress"):
            if key in card:
                print(f"  {key}: {card[key]}")
        caps = card.get("capabilities") or card.get("skills") or []
        if caps:
            print(f"  capabilities: {', '.join(str(c) for c in caps)}")
        print()
    if rate:
        print("## rate card")
        print(json.dumps(rate, indent=2)[:4000])
        print()

    print("## next steps")
    print("  1. Verify serviceExecutiveAddress OUT OF BAND (Metaplex-published")
    print("     value via an independent channel) before any delegation.")
    print("  2. Use `nori.py call ...` to print the exact curl for a service,")
    print("     then run it yourself after the user approves the exact spend.")


def curl_cmd(url, payload):
    parts = ["curl", "-sS", "-X", "POST", url,
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)]
    return " ".join(shlex.quote(p) for p in parts)


def cmd_call(args):
    base = args.url.rstrip("/")
    if args.service == "chat":
        url = base + "/v1/chat/completions"
        payload = {
            "model": args.model,
            "messages": ([{"role": "system", "content": args.system}] if args.system else [])
            + [{"role": "user", "content": args.prompt}],
        }
        note = "OpenAI-compatible chat.completion (non-streaming, tool calls supported)."
    elif args.service == "image":
        url = base + "/v1/images/generations"
        payload = {"model": "openai/gpt-image-1", "prompt": args.prompt}
        if args.size:
            payload["size"] = args.size
        note = "image.generation — flat per-image price, check the rate card."
    elif args.service == "rpc":
        url = base + "/v1/solana/rpc"
        try:
            params = json.loads(args.params) if args.params else []
        except json.JSONDecodeError as e:
            sys.exit(f"error: --params must be valid JSON: {e}")
        payload = {"jsonrpc": "2.0", "id": 1, "method": args.method, "params": params}
        note = "solana.rpc — transparent JSON-RPC pass-through incl. DAS (getAsset, getAssetsByOwner)."
    else:
        sys.exit(f"error: unknown service {args.service}")

    print(f"# DRY RUN — {note}")
    print("# This command was NOT executed. Review the price, get the user's")
    print("# explicit approval of the exact spend, then run it yourself.\n")
    print(curl_cmd(url, payload))


def main():
    ap = argparse.ArgumentParser(description="Nori helper: discovery + dry-run curl builder.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="fetch agent card + rate card (read-only)")
    d.add_argument("--url", required=True, help="NORI_URL base, e.g. https://nori.example.com")
    d.set_defaults(fn=cmd_discover)

    c = sub.add_parser("call", help="print the exact curl for a service call (dry-run only)")
    c.add_argument("service", choices=["chat", "image", "rpc"])
    c.add_argument("--url", required=True, help="NORI_URL base")
    c.add_argument("--model", default="openai/gpt-5.4", help="chat model as <provider>/<model>")
    c.add_argument("--prompt", default="Say hello in one sentence.",
                   help="prompt (chat) or image description (image)")
    c.add_argument("--system", default=None, help="chat system prompt")
    c.add_argument("--size", default=None, help="image size, e.g. 1024x1024")
    c.add_argument("--method", default="getBalance", help="rpc method")
    c.add_argument("--params", default=None, help="rpc params as JSON array")
    c.set_defaults(fn=cmd_call)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
