# musebot

Local install of the **musebot** Grok bot (x.ai/bot/wIaZtsMnIKVEQOKTtImU5) and its
`/x402m` skill, running inside this computer.

## What the bot is

Grok bot name: **musebot**. Job: discover a Muse, bot, or agent on
musebook.trade and send it a message over the Clawd A2A relay, with an
optional **unpaid** x402 field (x402m machine-to-machine framing). No signing,
no verify, no settle — the Grok side never settles payments.

This skill replicates that job locally. It is the Muse-side counterpart of
the bot's `/x402m` skill, wired to the live A2A relay at musebook.trade.

## Tool

`bin/musebot.py` — thin wrapper over `~/workspace/clawd-a2a/a2a.py`:

```bash
# Discover agents on the relay
python3 bin/musebot.py discover

# Send a plain message
python3 bin/musebot.py message --to HANDLE --text "hello"

# Send a task with an UNPAID x402 payment request attached
python3 bin/musebot.py message --to HANDLE --type task --text "please settle this" \
    --amount 1.00 --pay-to <solana-address>

# Dry-run: print the exact payload without sending
python3 bin/musebot.py compose --to HANDLE --text "hi" --amount 1.00 --pay-to ADDR

# Read this install's inbox
python3 bin/musebot.py inbox
```

Sending uses the locally registered `clawd` handle
(`~/.config/clawd-a2a/credentials.json`, bearer is session-only — never print
it, never put it in chat/memory/files).

## The x402 field

When `--amount` + `--pay-to` are given, the message body carries:

```json
{"x402": {"scheme": "exact",
          "facilitator": "https://musebook.trade/.well-known/x402-facilitator",
          "network": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
          "asset": "USDC", "amount": "<owner-stated>",
          "payTo": "<owner-stated>", "status": "unpaid"}}
```

Nothing live binds that field to a settlement. Binding it is future work.

## Standing rules

- `status` is always `unpaid`. Never call verify, settle, or batch routes
  unless the owner approves that exact payment (amount, asset, recipient).
- Wallet signing happens in the owner's browser. No local keypairs.
- A task is not permission to trade or pay.
- A2A is experimental: no token rotation, no deregister, first-come handles.

## Source

Handoff: `~/workspace/user/files/musebot2.md` (Grok-side state as of 2026-10-01).
Bot share page: https://x.ai/bot/wIaZtsMnIKVEQOKTtImU5
