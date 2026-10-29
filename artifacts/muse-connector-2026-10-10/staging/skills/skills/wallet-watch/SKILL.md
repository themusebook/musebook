---
name: wallet-watch
description: Read-only Solana wallet balance snapshots — SOL + SPL tokens with USD values via Jupiter pricing. Wallets come from your own config file; nothing is ever signed or moved.
version: 1.0.0
---

# Wallet Watch

One script, one job: print a chat-friendly balance summary for YOUR Solana
wallets. Read-only — it never signs, transfers, or trades.

## Setup (one time)

Create `wallets.json` next to `bin/balances.py` (or point
`$WALLET_WATCH_CONFIG` at it, or use `~/.config/clawd/wallets.json`):

```json
{
  "wallets": {
    "my-trader": "<solana address>",
    "my-savings": "<solana address>"
  },
  "symbols": {
    "<token mint>": "MYTOKEN"
  }
}
```

`symbols` is optional — it labels token mints you care about; anything else
prints as a shortened address. The Helius connector (main skill §1) supplies
RPC; Jupiter's public price API supplies USD values (no key).

## Run

```bash
python3 ~/.muse/skills/wallet-watch/bin/balances.py
```

Prints per-wallet SOL, token holdings with USD values, subtotals, and a
grand total. If price lookup fails it says so instead of inventing numbers.

## Suggested schedule

Hourly balance report to the user:

| Cadence | Command |
|---|---|
| hourly | `python3 ~/.muse/skills/wallet-watch/bin/balances.py` → deliver the printed summary as the report, keeping its formatting |

Rules: read-only task. If the script fails, say the check failed — never
invent balances. Never sign, transfer, or trade from this job.

## Tests

- With no `wallets.json`: exits with a helpful error and an example config.
- With a config: prints the summary; totals reconcile per-wallet subtotals.
