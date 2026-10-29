---
name: "ore-miner"
description: "Deploy your own ORE v3 grid miner on Solana mainnet. Hardened bot with per-round caps, daily caps, reserve floor, idempotency, and a fail-closed advisory gate. Dry-run first, fund, then go live."
---

# ORE Miner

Run your own miner for the ORE v3 grid protocol on Solana mainnet:
each round, deploy SOL across 25 tiles; on-chain entropy picks a winning
tile; winners split 1 ORE (+ SOL rebates). Full protocol spec in
`PROTOCOL.md` (verified live 2026-09-27).

**This is a participation miner, not a profit guarantee.** Losers get
~89.1% of deployed SOL back; winners get 99% + a share of the ORE reward.
The caps are the risk control. Never deploy more than you can lose.

## Dependencies

```bash
pip install solders pynacl
```

## Step 0 — Create the miner wallet

```bash
export ORE_MINER_KEYFILE=~/.ore-miner/keypair.enc
mkdir -p ~/.ore-miner && chmod 700 ~/.ore-miner
python3 bin/ore_miner.py --setup
```

Generates a new keypair, encrypts it with a password **you choose**
(never share it, never paste it in chat), and stores it at
`ORE_MINER_KEYFILE` with 0600 permissions. The password is asked
interactively on every run and never stored.

## Step 1 — Fund it

Send **0.10 SOL** to the printed miner address. That covers the default
0.05 SOL/day cap plus the 0.01 SOL reserve floor plus fees, with headroom.

## Step 2 — Dry-run (always first)

```bash
python3 bin/ore_miner.py --dry-run --once
```

Fetches live board state and simulates a round with zero spend. Confirm the
output shows a sane round/slot before going live.

## Step 3 — Go live

```bash
python3 bin/ore_miner.py --live --once
```

Runs one live round (default 0.01 SOL across 25 tiles). For continuous
mining, run without `--once` (loops rounds) or schedule it.

## Safety architecture (always on)

1. **Deterministic gates** — per-round cap (default 0.01 SOL), UTC daily
   cap (default 0.05 SOL), wallet reserve floor (default 0.01 SOL),
   per-round idempotency (never double-deploy a round), checkpoint-before-
   new-round enforcement.
2. **Advisory gate** — on installs with the TypeSafe connector, every
   deploy passes a fail-closed consistency check; any failure vetoes the
   round. On installs without it, live deploys require the explicit
   operator override `--force-no-jev` (the deterministic caps still apply).
3. **Durable intents** — every planned deploy is persisted before
   broadcast; on-chain state gives crash-safe idempotency.

## Useful commands

```bash
python3 bin/ore_miner.py --checkpoint-only   # claim SOL winnings for a finished round
python3 bin/ore_miner.py --claim-only        # sweep claimable ORE/SOL
python3 bin/ore_miner.py --live --cap-sol 0.005 --daily-cap-sol 0.02  # tighter caps
```

## Notes

- ORE claim takes a 10% protocol fee; with auto-return the checkpoint
  sends SOL winnings straight to the wallet.
- Rounds are ~96s; don't run two miner instances against the same keyfile.
- Mainnet only. There is no testnet ORE.
