---
name: clawd-jev-trading
description: Paper-trading machine for Solana spot with a TypeSafe JEV decision brain, dynamic venue action space, CoinGecko regime context, and Supermemory recall. Dry-run only — live execution is refused by design.
---

# clawd-JEV-trading machine

A small, honest paper-trading machine for SOL on Solana venues. One TypeSafe
`jev-latest` call per cycle picks a single action; code owns routing, sizing,
risk, and simulation. Nothing here signs, broadcasts, or executes — the
`live` command refuses with exit code 2 by design.

Repo: https://github.com/Solizardking/clawd-jev-trading-machine (public, MIT)

## How it works

1. **Probe venues** — each cycle the machine quotes every configured venue and
   builds the action space *dynamically*: Jupiter (keyless quotes), DFlow
   (needs `DFLOW_API_KEY` and a good quote), Imperial (excluded until its feed
   is wired). `WAIT` / `OPEN_REVIEW` / `BLOCKED` are always offered. A venue
   that can't be quoted can't be chosen.
2. **Regime context** — CoinGecko market data is fetched (optional
   `COINGECKO_API_KEY`) and reduced to a labeled regime
   (`RISK_ON` / `RISK_OFF` / `CHOP` / `UNKNOWN`) with raw numbers attached.
   Missing data is labeled `UNKNOWN`, never invented.
3. **Memory recall** — before the JEV call, recent outcomes are recalled from
   Supermemory (`SUPERMEMORY_API_KEY`); after the simulated outcome, the
   result is written back. Key absent → memory disabled, labeled honestly.
4. **One JEV decision** — the full state (quotes, tape, regime, recalled
   memory, risk caps) goes to `POST https://api.typesafe.ai/v1/systemone`
   (model `jev-latest`, Bearer `TYPESAFE_API_KEY`) as a typed `choice`
   question over exactly the offered actions. Unknown or stale choices fail
   closed to `BLOCKED`.
5. **Dry-run fill** — the decision is simulated against the quotes; fills,
   rejections, and skips are recorded to JSONL. `backtest` replays recorded
   decisions into JSON + HTML reports, labeled as simulated fills.

When TypeSafe is unreachable the machine runs in an explicitly labeled
**mock mode** (deterministic rule-based decisions) instead of failing.

## Quickstart

```bash
git clone https://github.com/Solizardking/clawd-jev-trading-machine.git
cd clawd-jev-trading-machine
cp .env.example .env   # fill in keys; never commit .env

python3 -m clawd_jev doctor                      # env, venues, action space
python3 -m clawd_jev paper --dry-run-mock --iterations 2
python3 -m clawd_jev backtest --decisions runtime/paper-*/decisions.jsonl
python3 -m clawd_jev live                       # refuses: exit 2, by design
```

## Environment

| Variable | Purpose | Required |
|---|---|---|
| `TYPESAFE_API_KEY` | TypeSafe `jev-latest` decision brain | No (mock mode without it) |
| `DFLOW_API_KEY` | DFlow quotes (adds DFlow actions to the space) | No |
| `COINGECKO_API_KEY` | CoinGecko regime data (demo/pro header) | No |
| `SUPERMEMORY_API_KEY` | Memory recall + outcome writes | No |

Keys are read at call time from the environment, never logged, never
persisted to reports. `.env.example` documents names only — no values.

## Safety rules (non-negotiable)

- Paper mode only. No private keys, no signing, no broadcasting anywhere in
  the codebase.
- `live` always refuses until a future version wires an explicitly approved
  venue, asset, cap, and signing path.
- Every TypeSafe choice is validated against the exact action table offered
  that cycle; anything else becomes `BLOCKED`.
- Regime `UNKNOWN` and memory-disabled states are labeled in the state
  payload — the brain sees what's missing.
- Reports say "simulated fills" — never profitability claims, never live
  trading claims.
