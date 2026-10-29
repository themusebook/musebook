---
name: imperial-portfolio-intel
description: Imperial profile balances, open positions, open orders, exposure summary, cross-margin seat state, Touch contracts, and wallet-level Telegram/admin portfolio recaps.
---

# Imperial Portfolio Intel

Parent skill `imperial` holds the full API reference.

## Endpoints

- `GET /api/v1/mobile/balances` (JWT) — per-profile USDC, 6-decimal native units.
- `GET /api/v1/positions?walletAddress=` (+`underwriter` filter) — open lifecycles
  across every underwriter. Carries `phoenixCrossSeats[]` per profile: margin
  figures and positions from the same instant (do NOT mix with a separately
  polled `/phoenix/margin-account` read when computing risk).
- `GET /api/v1/orders?walletAddress=` — open orders; `GET /order-history` and
  `/order-history/{order_pda}` for the full lifecycle incl. canceled/filled.
- `GET /api/v1/passthrough/users/{wallet}/orders` — passthrough subset
  (`status`, `profile_index`, `limit` filters).
- `GET /api/v1/trades?walletAddress=` — open + closed lifecycles with actions,
  fees, realized PnL. `GET /pnl-history` (`resolution` 1h|1d) for bucketed PnL.
- `GET /api/v1/funding-history`, `/deposit-history` — paid/received funding and
  deposit/withdraw/transfer events (filters: market, underwriter, side,
  direction, profileIndex, time bounds).
- `GET /api/v1/phoenix/margin-account?walletAddress=&profileIndex=` — the
  cross-margin seat: `accountCollateralUsd`, `effectiveCollateralUsd`,
  `initialMarginUsd`, `maintenanceMarginUsd`, `riskState`, `riskTier`,
  `maxPositions`/`openPositions`, `liquidationPricesBySymbol` (Phoenix-raw
  symbols, e.g. GOLD; null = unknown, NEVER 0). Null response = profile never
  onboarded (not an error).
- `GET /api/v1/phoenix/direct-positions?walletAddress=` — wallet-owned Phoenix
  positions independent of the Imperial indexer.
- `GET /api/v1/touch/positions?walletAddress=` — Touch binaries. These appear
  ONLY here — absent from `/positions`, `/trades`, `/orders`, `/stats/*`, and
  both WS streams. Status: `open` → `settled` (`won`) or `bought_back`.
- `GET /api/v1/mobile/points` (JWT) — Imperial points, active season.
- Platform: `/stats/summary`, `/stats/markets`, `/stats/volume`,
  `/stats/open-interest` (+`/history`).

## Reporting rules

- Always state which `profileIndex` or wallet scope the summary refers to.
- On cross-margin rows, per-position liquidation fields are null — report
  `liquidationPricesBySymbol` instead, and never compute seat risk from
  per-leg `collateralUsd`/`leverageX`.
- Key local state on `(positionPda, asset, side)` — on a cross seat,
  `positionPda` is the shared trader account.
- Open notional by symbol AND venue; open order count; outstanding close legs.
- For Telegram/admin recaps: balances, exposure, unrealized PnL, margin
  headroom, Touch contracts separately.
