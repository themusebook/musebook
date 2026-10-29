---
name: "clawd-live-bundle"
description: "The full-stack Clawd onboarding bundle: live relay connection, Solana onboarding, browser-first wallet setup/generation, Phoenix perps registration, live trading workflows, and pump.fun agent flows — all wired into the connector."
---

# Clawd Live Bundle

This skill is the index for the full-stack onboarding bundle. It does not
duplicate other skills — it wires them together into one ordered path.

## 1. Live Clawd relay

Connect to the live trench for real-time launch/event streams:

- Base: `https://clawd-ws.fly.dev`
- WebSocket: `wss://clawd-ws.fly.dev/ws`

Verified live 2026-09-19: HTTPS 200, WS handshake 101 with live
`token-launch` frames. The relay feeds **OBSERVE** only — it never bypasses
freshness, schema, mandate, or risk checks before execution.

## 2. Solana onboarding

- RPC: Helius (`helius` skill) for reads; public endpoints as fallback.
- Identity/registry: Metaplex Agent Registry (`solana-agent-registration`,
  `musebook` skills).

## 3. Browser-first wallet setup / generation

- Default: **all wallet signing happens in the user's browser**.
- Wallet generation is bundled but never runs automatically during install.
- Key generation reference: `pump-solana-wallet` skill (Ed25519, offline).
- Approved scoped local-wallet exceptions only: `clawd-buyer`,
  `dflow-trader`, `phoenix-trader`. Do not extend to new venues without
  asking.

## 4. Phoenix perps registration

- Use the `phoenix` skill: `quote` prints exact registration cost, then
  `register --wallet <name> --max-positions 32 --yes` (build → partial-sign
  → onboarder co-sign → confirm → verify).
- Funding the wallet ≠ depositing collateral — margin deposit is a separate
  approved step.
- Live trading: `vulcan-trade-execution` (Phoenix) and
  `imperial-trade-execution` (Imperial router) — every order needs separate
  approval of market, side, size, and order type.

## 5. Live trading workflows

- Spot swaps: `dflow-spot-trading`, `jupiter`, `pump-agents-swap`.
- Prediction markets: `dflow-kalshi-trading`.
- Pre-trade diligence: `rug-check`, `risk-manager`, `meme-token-analyzer`,
  `alpha-scanner`, `whale-tracker`.

## 6. pump.fun agent flows

- `pump-agents-create-coin` — launch a coin (+ optional initial buy).
- `pump-agents-swap` — buy/sell bonding-curve and AMM tokens.
- `pump-agents-fees` — creator fees, cashback, sharing configs.
- `pump-agents-payments` — SOL/USDC invoices via
  `@pump-fun/agent-payments-sdk`, verified on-chain before service.
- Monitoring: `pumpfun-live` (WS launch stream).

## Safety (bundle-wide)

- Browser-first signing; agent never signs for the user on pump.fun flows.
- No trade, transfer, registration, deposit, swap, or payment without the
  user's fresh approval of exact terms.
- Jito-only transactions never leak through public RPC.
- Market material is research/education, not personalized financial advice.
