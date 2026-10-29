---
name: "phoenix"
description: "Use Phoenix when the user asks for Phoenix, phoenix perps, or phoenix perpetuals market data."
---

# Phoenix

## Purpose
Read Phoenix perpetual futures market data on Solana via the official
Vulcan CLI, and execute live perps trades with the user's explicitly
approved local wallet (see Auth). Supports read-only market data
(public, no auth), technical indicator computation, public trade
history, local paper trading, and live order placement.

## Tooling
A Python CLI lives under `~/workspace/skills/phoenix/bin/`:

```
bin/phx.py <command> [args...]
```

It shells out to `vulcan` with `-o json` and passes JSON through.
Read-only subcommands: `market` (list, info, ticker, orderbook,
candles, trades, funding-rates), `ta` (compute, signal, report),
`history` (trades, orders, collateral, funding, pnl), and `paper`
(local simulated trading against live prices, no wallet touched).
Live trading goes through `vulcan` directly (order placement,
cancels, stop-loss/conditional orders) — see Operating Rules.

## Trader onboarding (one-shot registration)

New traders register through `bin/register_trader.py` — the verified
mainnet flow (2026-09-18) that needs no referral code:

```
register_trader.py quote --authority <PUBKEY> [--max-positions 32]
register_trader.py register --wallet <VULCAN_WALLET_NAME> --max-positions 32 --yes
```

1. `quote` — prints the EXACT registration cost (rent + 2-signature
   fee) from the on-chain rent model; no wallet, no signing. If the
   authority is already funded it also cross-checks the figure with a
   live mainnet simulation.
2. `register` — balance check → build register instructions →
   partial-sign with the authority (the Phoenix onboarder slot stays
   empty) → `POST /v1/exchange/send-register-ixs` (Phoenix co-signs +
   broadcasts) → confirm → verify via trader state. Requires `--yes`.

Exact costs (measured on mainnet 2026-09-18): 32 positions = 0.00837184
SOL rent; 128 positions = 0.02787904 SOL rent; + 0.00001 SOL network fee
(authority + onboarder signatures). The API rejects maxPositions < 32.

- Always run `quote` first and get the user's explicit approval of the
  EXACT total before `register`.
- The wallet password is supplied transiently (VULCAN_WALLET_PASSWORD
  env or interactive prompt) and is used only in memory; it is never
  stored, logged, or repeated in chat.
- Collateral deposit (margin) is a SEPARATE step and approval — funding
  the wallet does not deposit margin.
- If the authority is already registered, the command reports that and
  does nothing.

Docs index: `~/workspace/skills/phoenix/docs/llms.txt` (fetched
2026-09-17 from https://docs.phoenix.trade/llms.txt). Endpoint reference:
`~/workspace/skills/phoenix/docs/api-exchange-endpoints.md` (exchange,
markets, orderbook, mark-price, stats history, register-ixs builders;
added 2026-09-18) and
`~/workspace/skills/phoenix/docs/api-trader-endpoints.md` (trader view,
trader state snapshot, user/trader PnL, portfolio values, per-market PnL,
wallet auth challenge/nonce; added 2026-09-18).

## Auth
Local wallet `phoenix-trader` (created 2026-09-17, user-approved scoped
exception to the browser-signing rule — perps only):

- Pubkey: `CiHQZcf8nmn1uLyW4bctZkNef7G1KBr5wYx5cNnJudoU`
- Encrypted file: `~/.vulcan/wallets/phoenix-trader.json` (0600)
- Set as the default vulcan wallet.
- Live-signing commands require `VULCAN_WALLET_PASSWORD` in the
  environment. The password is **never stored** — the user supplies it
  transiently per session, it is used once via env var, then unset.
  Never write it to disk, log it, or repeat it in chat.
- The wallet must be funded (SOL for fees/rent + USDC collateral via
  the Phoenix deposit flow) before any live trade.

## Operating Rules
1. Use this skill when the user asks for Phoenix / Phoenix perps.
2. Never import, export, or remove the wallet; never run `vulcan setup`
   again (wallet already exists).
3. Never place a live order without the user's explicit approval for
   that specific trade (market, side, size, order type). Paper mode
   needs no approval.
4. Never use `--auto-execute` or any unattended/auto trading mode.
5. Every live-signing command needs the wallet password supplied
   transiently by the user for that session; if it is not available,
   stop and ask instead of working around it.
6. `paper` mode remains the default for exploration and demos; it never
   touches the wallet or on-chain state.
7. Treat all data and flows here as research/education, never trading
   advice. No personalized buy/sell recommendations.
