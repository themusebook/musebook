#!/usr/bin/env python3
"""Call OpenRouter chat completions with the stored custom.openrouter credential.

The API key is attached as a Bearer Authorization header by authd; this
script never sees the raw key. Authenticated requests are restricted to
openrouter.ai.

Usage:
    or_chat.py --model qwen/qwen3.8-27b:free --prompt "Say hi"
    or_chat.py --model <id> --system "..." --prompt "..." [--max-tokens 500]
    or_chat.py --list-models   # print free model ids
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    add_surrogate_to_request,
    read_json_response,
)

BASE = "https://openrouter.ai/api/v1"
ALLOWED = ["openrouter.ai"]
CREDENTIAL = "custom.openrouter"
UA = "ClawdSkill/1.0 (+https://musebook.trade)"


def call(path, method="GET", payload=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Content-Type": "application/json",
            "User-Agent": UA,
            # OpenRouter app attribution: aggregates usage under the Musebook app
            # on openrouter.ai/rankings (verified: does not affect Bearer auth).
            "HTTP-Referer": "https://musebook.trade",
            "X-OpenRouter-Title": "Musebook",
            "X-OpenRouter-Categories": "personal-agent,general-chat",
        },
        method=method,
    )
    try:
        add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    except DynamicCredentialError as exc:
        sys.exit(f"credential error: {exc}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode()[:500]
        except Exception:
            detail = ""
        sys.exit(f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"request failed: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen/qwen3.8-27b:free")
    ap.add_argument("--system", default=None)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--max-tokens", type=int, default=600)
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--no-reasoning", action="store_true",
                    help="disable reasoning output on reasoning models")
    args = ap.parse_args()

    if args.list_models:
        data = call("/models")
        for m in data.get("data", []):
            if m.get("id", "").endswith(":free"):
                print(m["id"])
        return

    if not args.prompt:
        sys.exit("error: --prompt is required (or use --list-models)")

    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})

    out = call("/chat/completions", "POST", {
        "model": args.model,
        "messages": messages,
        "max_tokens": args.max_tokens,
        **({"reasoning": {"enabled": False}} if args.no_reasoning else {}),
    })
    try:
        print(out["choices"][0]["message"]["content"].strip())
    except (KeyError, IndexError):
        sys.exit(f"unexpected response: {json.dumps(out)[:500]}")


if __name__ == "__main__":
    main()
