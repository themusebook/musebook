#!/usr/bin/env python3
"""musebot — local install of the x.ai musebot Grok bot's /x402m skill.

Replicates what the Grok bot does: discover agents on musebook.trade and
send them messages over the Clawd A2A relay, with an optional UNPAID x402
field (x402m machine-to-machine framing). No signing, no verify, no settle.

Usage:
  musebot.py discover
      List agents on the A2A relay.

  musebot.py message --to HANDLE --text "hello" [--type task|message|result]
                     [--amount 1.00 --pay-to <solana-address>]
      Send a message. With --amount/--pay-to, attaches the unpaid x402 object.
      The x402 field is informational only — nothing is verified or settled.

  musebot.py inbox [--wait-s N]
      Read this install's inbox (uses the local clawd handle credentials).

  musebot.py compose --to HANDLE --text "hello" --amount 1.00 --pay-to ADDR
      Print the exact send payload without sending (dry run).

Standing rules (from the bot's handoff):
- The x402 object is always status=unpaid. Never call verify/settle/batch
  routes unless the owner approves that exact payment (amount, asset, recipient).
- Wallet signing happens in the owner's browser. No local keypairs.
- The A2A bearer in ~/.config/clawd-a2a/credentials.json is session-only:
  never print it, never put it in chat, memory, or files.
"""
import json
import subprocess
import sys

A2A = ["python3", "/home/hatch/workspace/clawd-a2a/a2a.py"]
FACILITATOR = "https://musebook.trade/.well-known/x402-facilitator"
NETWORK = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"


def x402_unpaid(amount, pay_to, asset="USDC"):
    return {
        "scheme": "exact",
        "facilitator": FACILITATOR,
        "network": NETWORK,
        "asset": asset,
        "amount": str(amount),
        "payTo": pay_to,
        "status": "unpaid",
    }


def build_body(text, msg_type, amount=None, pay_to=None):
    body = {"text": text}
    if amount is not None and pay_to is not None:
        body["x402"] = x402_unpaid(amount, pay_to)
    elif amount is not None or pay_to is not None:
        raise SystemExit("error: --amount and --pay-to must be given together")
    return body


def run_a2a(*args):
    p = subprocess.run(A2A + list(args), capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    if p.returncode != 0:
        sys.stderr.write(p.stderr)
    return p.returncode


def main():
    import argparse
    ap = argparse.ArgumentParser(prog="musebot.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("discover", help="list agents on the A2A relay")

    m = sub.add_parser("message", help="send a message to a handle")
    m.add_argument("--to", required=True)
    m.add_argument("--text", required=True)
    m.add_argument("--type", default="message", choices=["task", "message", "result"])
    m.add_argument("--amount", help="USDC amount for the UNPAID x402 field")
    m.add_argument("--pay-to", help="recipient address for the UNPAID x402 field")
    m.add_argument("--thread")

    i = sub.add_parser("inbox", help="read inbox")
    i.add_argument("--wait-s", type=int, default=0)

    c = sub.add_parser("compose", help="print send payload without sending")
    c.add_argument("--to", required=True)
    c.add_argument("--text", required=True)
    c.add_argument("--type", default="message")
    c.add_argument("--amount")
    c.add_argument("--pay-to")

    args = ap.parse_args()

    if args.cmd == "discover":
        sys.exit(run_a2a("agents"))

    if args.cmd == "inbox":
        a = ["inbox"]
        if args.wait_s:
            a += ["--wait-s", str(args.wait_s)]
        sys.exit(run_a2a(*a))

    if args.cmd == "compose":
        body = build_body(args.text, args.type, args.amount, args.pay_to)
        print(json.dumps({"to": args.to, "type": args.type, "body": body}, indent=2))
        return

    if args.cmd == "message":
        body = build_body(args.text, args.type, args.amount, args.pay_to)
        a = ["send", "--to", args.to, "--type", args.type,
             "--body", json.dumps(body)]
        if args.thread:
            a += ["--thread", args.thread]
        print(f"sending {args.type} to {args.to}"
              + (" (with UNPAID x402 field)" if "x402" in body else ""), file=sys.stderr)
        sys.exit(run_a2a(*a))


main()
