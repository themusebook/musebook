---
name: imperial-trade-execution
description: Safe Imperial live execution: authenticated market/limit/stop orders, Phoenix-first venue preference, profile-aware routing, batch entry+TP/SL, Imperial Touch binaries, and post-trade verification.
---

# Imperial Trade Execution

Endpoints: `POST /api/v1/mobile/orders`, `/mobile/orders/batch`,
`/mobile/orders/cancel`, `/mobile/orders/collateral`, `/mobile/orders/preflight`,
`/mobile/orders/update`. Parent skill `imperial` holds the full API reference.

## Before any live order

1. Run `imperial-risk-management` checks (balances, positions, funding/route).
2. Run `POST /mobile/orders/preflight` with the EXACT body you intend to place.
3. Get explicit user approval of exact terms: side, venue, size, leverage,
   profileIndex, slippage.

## Order body essentials

- Required: `wallet` (matches JWT claim), `profileIndex`, `underwriter`,
  `side` (0 long / 1 short), `action` (0 Increase / 1 Decrease), `orderType`,
  `fundingStatus` (0), `priority`, `collateralAmount`, `sizeUsd` (6-decimal),
  `slippageBps`, `triggerPrice` (oracle ×1e9), `triggerCondition` (0 Above /
  1 Below). One of `symbol` (canonical: `SOL`, `XAU`) or `marketMint`.
- `marketPrice` scale is per-underwriter: Jupiter/Phoenix/Pairs/Armada ×1e6,
  GMTrade ×1e9, Touch ignored (0). Send a live price — on Armada it becomes the
  on-chain `expected_price` for both price bands.
- Default open: `action=0, orderType=0, fundingStatus=0, underwriter=2`
  (Phoenix) unless requested otherwise. Default close: `action=1, orderType=0`,
  same wallet + profile as the open.
- Closes: use `closeBps: 10000` for a full close (or `sizeUsd: 0` with closeBps
  omitted). NEVER echo the open's `sizeUsd` — oracle drift turns it into dust
  the venue rejects (`ReduceBelowMinCollateral` / `MinCollateral`).

## Always verify

- Response `success` (HTTP 200 lies — inspect the body), `errorCode` on failure.
- Transaction `signature` on success.
- Follow-up state via `GET /positions`, `/orders`, or the `/ws` stream.
- Resting orders return `orderPda` — usable immediately for cancel/update.

## Advanced shapes

- **Batch** (`/mobile/orders/batch`): `{entry, closeOrders[]}` — entry plus
  attached TP/SL/ratchet/DCA-close legs in one request. All legs share one
  builderCode or none.
- **Phoenix-native maker**: `phoenixNative: true` (underwriter 2 + Limit/Increase
  or PrivateTpSl). Post-only, no update (cancel + replace), partial fills OK —
  poll or watch `/ws`; placement ≠ fill.
- **Touch binaries** (underwriter 6): buy = `action: 0, orderType: 0`,
  `triggerPrice` = barrier ×1e9, `sizeUsd` = payout µUSD, `collateralAmount` =
  premium budget µUSD, `slippageBps: 0`. Sell-back = `action: 1`,
  `triggerPrice` = positionId + 1 (NOT scaled), `sizeUsd` echoed byte-for-byte.
- **Armada** (underwriter 7): non-zero `slippageBps` required on opens;
  `quoteId` from `/armada/quote` binds the server quote to the order;
  `requestedHedgeVenue` 0 = auto, 1 = current route.
- **Collateral add/remove** (`/mobile/orders/collateral`): on a Phoenix cross
  seat, `marketMint`/`side` name any open market (transport only).

## Collateral currency

USDC only for deposits (`/deposit/build-tx`; wrap SOL → WSOL client-side).
After closing Jupiter long-custody positions, reclaim WSOL/WBTC/WETH residue via
`POST /passthrough/users/{wallet}/profiles/{index}/sync`.
