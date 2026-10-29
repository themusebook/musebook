---
name: imperial-risk-management
description: Risk checks for Imperial-routed perps: profile funding, existing exposure, venue choice, margin headroom, preflight, cross-seat admission, and Telegram pre-trade snapshots.
---

# Imperial Risk Management

Parent skill `imperial` holds the full API reference. Run these checks before
ANY live trade, in order:

1. **Funding** — `GET /mobile/balances`: per-profile USDC vs. the intended
   `collateralAmount`. Uninitialized profiles read 0 (normal).
2. **Exposure** — `GET /positions?walletAddress=`: existing same-symbol exposure
   on the same profile. Always present it before increasing.
3. **Venue/funding context** — `GET /funding-rates` (per-venue funding/borrow;
   longRate > 0 = longs pay shorts; Jupiter funding null, borrow ≥ 0) and
   `GET /route?asset=&side=&notional=` (cost-optimized venue; size deposits from
   its `requiredDeposit`, NOT from cost-breakdown expectations).
4. **Preflight** — `POST /mobile/orders/preflight` with the exact order body.
   A green preflight is necessary, not sufficient: it is not a liquidation
   guarantee, and USDC balance alone does not prove leverage feasibility.
5. **Terms confirmation** — requested notional, side, venue, `profileIndex`,
   slippage, leverage. Explicit user approval of exact terms (standing rule).

## Venue-specific gates

- **Armada** (underwriter 7): opens require non-zero `slippageBps`; check
  `/armada/open-availability` first (advisory); `marketPrice` must be live —
  it becomes the on-chain `expected_price`.
- **Phoenix cross seat** (unified profile): admission is seat-wide —
  `free + collateralAmount ≥ sizeUsd / maxLeverage`
  (`free = effectiveCollateralUsd − initialMarginUsd` from
  `/phoenix/margin-account`; `maxLeverage` from `/phoenix/markets`). A position
  large enough for a lower leverage tier needs more. `collateralAmount: 0` is
  legal once the seat has headroom. Reject non-Phoenix underwriters, lending
  loans, and `isolatedOnly` markets on unified profiles.
- **Touch** (underwriter 6): check `halted` on `/touch/markets`; premium budget
  must cover the live ask or the fill is refused (`TouchQuoteMoved`) — nothing
  trades, just re-quote.
- **GMTrade**: `marketPrice` is ×1e9 (not ×1e6) — wrong scale collapses the
  slippage band.

## Pre-trade snapshot (Telegram / admin)

Balances per profile, open notional by symbol+venue, unrealized PnL, margin
headroom (seat-wide on cross), funding direction/cost for the intended hold,
preflight result, and the exact terms awaiting approval. One message, no
separate "are you sure" round-trips beyond the approval itself.
