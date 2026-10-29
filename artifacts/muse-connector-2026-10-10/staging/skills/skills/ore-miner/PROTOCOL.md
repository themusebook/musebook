# ORE Miner v2

Automated deploy/checkpoint/claim bot for the ORE v3 grid protocol on Solana
mainnet, with a TypeSafe JEV advisory gate on every deploy.

## Protocol (verified live 2026-09-27)

- Program: `oreV3EG1i9BEgiAJ8b177Z2S2rMarzak4NMv1kULvWv` (steel, NOT Anchor)
- Mint: `oreoU2P8bN6jkk3jbaiVxYnG1dCXcYxwhwyK9jSybcp` (11 decimals)
- Entropy program: `3jSkUuYBoJzQPMEzTvkDFXCZUBksPamrVhrnHR9igu2X`
- Round: 240 slots (~96s); intermission 48 slots
- Each round: deploy SOL onto 25 tiles → onchain entropy picks one winning
  tile → 1 ORE to the winning tile's miners (proportional) + 0.2 ORE to the
  Motherlode
- 15 split tiles + 10 solo tiles (solo mask derived from the round's slot
  hash via the program's Keccak/Fisher-Yates algorithm — reproduced exactly)
- Winners get 99% of deployed SOL back; losers 89.1%

### Account discriminators (steel u64 LE, observed live)

| Account | Discriminator | Length |
|---------|--------------|--------|
| Board   | 105          | 40     |
| Config  | 101          | 232    |
| Round   | 109          | 952    |
| Miner   | (recorded on first deploy) | 752 |

The bot asserts these on every decode and aborts on mismatch.

## Strategy

Even spread across all 25 tiles (`0x1FFFFFF` mask). `--cap-sol` is the
**per-round total** (default 0.01 SOL), split as `cap // 25` lamports per tile.

Expected average SOL return ≈ 89.5%/round; the 1 ORE round reward (split
among winners on the winning tile, proportional to deployment) must exceed
the ~10.5% bleed for profitability. **This is a participation miner, not a
profit guarantee. Caps are the risk control.**

Claim note: `claimOre` takes a 10% protocol fee on unrefined rewards;
with `auto_return=1` the checkpoint sends SOL winnings straight to the
wallet, so `claimSol` is normally a no-op safety net.

## Safety architecture

1. **Deterministic gates** (code, always on): per-round cap, UTC daily cap
   (default 0.05 SOL = 5 rounds/day), wallet reserve floor (default 0.01
   SOL), per-round idempotency (never redeploy a round), altered-mask retry
   refusal, checkpoint-before-new-round enforcement.
2. **TypeSafe JEV advisory gate** (default on, mandatory for live): every
   deploy builds a structured telemetry state; JEV answers two questions —
   *do all listed invariants hold?* (noul, must be ≥ 0.75) and *is the
   telemetry internally consistent?* (noul, must be ≥ 0.6). Any JEV error,
   failed invariant, or inconsistency vetoes the round (fail-closed).
   JEV judges data consistency, never the economics, and can never
   authorize spending. Uses the `custom.typesafe` credential; the raw
   `TYPESAFE_API_KEY` never touches this code.
3. **Durable intents** (`state/intents.json`): every planned deploy is
   persisted before broadcast; on-chain miner state provides crash-safe
   idempotency.
4. **Simulation first**: every live deploy is simulated before broadcast;
   the checkpoint ix is simulated separately before being prepended.

## Usage

```bash
# 1. One-time wallet setup (prompts for password; NOTHING is funded)
ORE_MINER_KEYFILE=~/.vulcan/wallets/ore-miner.json \
ORE_MINER_PASSWORD=<transient> \
python3 ore_miner.py --setup

# 2. Dry-run: full pipeline incl. JEV gate + simulation (default, never sends)
python3 ore_miner.py --dry-run --once

# 3. Live single round (requires funded wallet + explicit approval)
ORE_MINER_KEYFILE=~/.vulcan/wallets/ore-miner.json \
ORE_MINER_PASSWORD=<transient> \
python3 ore_miner.py --live --once

# 4. Live loop
... python3 ore_miner.py --live

# Maintenance
python3 ore_miner.py --live --checkpoint-only   # checkpoint + claim only
python3 ore_miner.py --live --claim-only         # claim ORE/SOL only
```

`--no-jev` is dry-run only. Live without JEV requires the explicit
operator override `--force-no-jev`.

## Funding gate

The wallet is created UNFUNDED. No wallet exists yet; nothing is funded.

Funding requires the operator's explicit approval of exact terms: funding
amount, per-round cap, daily cap, reserve floor. The miner never moves
funds beyond: `deploy` (≤ round cap), `checkpoint`, `claimSol`, `claimOre`.

## Files

- `ore_miner.py` — the bot
- `state/stats.json` — round history, JEV verdicts, totals
- `state/intents.json` — durable deploy intents

## Verification notes

- Instruction encoding verified byte-for-byte against
  `regolith-labs/ore` (`api/src/instruction.rs`, `api/src/sdk.rs`,
  `program/src/deploy.rs`).
- Checkpoint instruction account order verified against
  `api/src/sdk.rs` (8 accounts: signer, authority, automation PDA, board,
  miner PDA, prior round PDA, treasury, system program).
- Mainnet simulation of an unfunded keypair returns `AccountNotFound`
  (payer has no account) — this is a simulation artifact, not an encoding
  error. Full end-to-end validation happens on first funded deploy.
- `deploy` auto-creates the Miner PDA on first use; the Automation PDA is
  optional (skipped when its data is empty).

## Status (2026-09-27)

- [x] Protocol reverse-engineered and verified against live accounts
- [x] Instruction builders match ore-api account ordering
- [x] Solo-tile mask reproduces the program's Keccak/Fisher-Yates exactly
- [x] Checkpoint lifecycle implemented and simulated
- [x] JEV gate integrated, tested live (passes healthy, vetoes tampered)
- [x] Dry-run pipeline green end-to-end
- [ ] Wallet creation (awaiting operator approval of exact terms)
- [ ] Funding (awaiting operator approval of exact terms)
- [ ] First live deploy
