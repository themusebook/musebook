# Phoenix Eternal public API — trader & auth endpoints

Source: https://docs.phoenix.trade (OpenAPI phoenix-public-api.json).
Base: https://perp-api.phoenix.trade
Pasted into the skill 2026-09-18.

## Documentation Index
Fetch the complete documentation index at: https://docs.phoenix.trade/llms.txt
Use this file to discover all available pages before exploring further.

Auth note: trader/history endpoints require the Phoenix bearer token
(`PhoenixBearerAuth`, issued by `/v1/auth/*` login endpoints). Public
exchange/market reads do not.

# Get trader

> Handles `GET /v1/view/trader/{pubkey}` via `get.v1.view.trader.by_pubkey`.

Full TraderView for one trader PDA (base58 pubkey in path): flags,
state (uninitialized|cold|active|reduceOnly|frozen), capability matrix
(placeLimitOrder, placeMarketOrder, riskIncreasingTrade,
riskReducingTrade, depositCollateral, withdrawCollateral — each with
`immediate` and `viaColdActivation`), authority, traderPdaIndex,
traderSubaccountIndex, collateralBalance, effectiveCollateral,
effectiveCollateralForWithdrawals, unrealizedPnl,
discountedUnrealizedPnl, unsettledFundingOwed, accumulatedFunding,
portfolioValue, maintenanceMargin, cancelMargin, initialMargin,
initialMarginForWithdrawals, riskState
(healthy|unhealthy|underwater|zeroCollateralNoPositions), riskTier
(safe|atRisk|cancellable|liquidatable|backstopLiquidatable|highRisk),
positions[] (per-symbol: positionSize, virtualQuotePosition, entryPrice,
unrealizedPnl, margins, liquidationPrice, optional takeProfitPrice /
stopLossPrice), limitOrders grouped by symbol, maker/taker fee override
multipliers, maxPositions, lastDepositSlot, isInActiveTraders,
numMarketsWithSplines, slot/slotIndex of the snapshot.

# Get trader state

> Handles `GET /v1/trader/state/{authority_pubkey}` via
> `get.v1.trader.state.by_authority_pubkey`.

Snapshot for every subaccount under a trader PDA. Path: authority
pubkey. Optional query: `traderPdaIndex` (default 0). Returns
TraderStateSnapshotResponse: authority, traderPdaIndex, slot, slotIndex,
snapshot { version, capabilities (flags + derived state), maker/taker
fee override multipliers, subaccounts[] }. Each subaccount snapshot:
subaccountIndex, sequence watermark, collateral (decimal string),
orders grouped by symbol, positions keyed by symbol (with TP/SL and
conditional trigger rows), splines, triggers, optional cooldownStatus
(withdrawal cooldown: lastDepositSlot + cooldownPeriodInSlots).

# Get user PnL

> Handles `GET /v1/users/{user_pubkey}/pnl` via
> `get.v1.users.by_user_pubkey.pnl`.

PnL time series keyed by user (authority) pubkey. Required query:
`resolution` (1m, 1d). Optional: startTime/endTime (ms epoch, max 1y
range), limit (default 1000, max 1440). Returns PnLPoint[]:
cumulativePnl, unrealizedPnl, cumulativeFundingPayment,
cumulativeTakerFee, startTime/endTime.

# Get trader portfolio values

> Handles `GET /v1/traders/{trader_pubkey}/portfolio-values` via
> `get.v1.traders.by_trader_pubkey.portfolio_values`.

Portfolio-value time series keyed by trader PDA pubkey. Required query:
`resolution` (1m testing only, 15m, 30m, 1h, 4h, 1d, 1w, 1M).
Optional: startTime/endTime (ms epoch, max 1y), limit (default 1440,
max 2000). Returns PortfolioValuePoint[]: value plus optional
per-market positions snapshot (baseLots, quoteLots, positionValue,
initialMargin).

# Get trader PnL

> Handles `GET /v1/traders/{trader_pubkey}/pnl` via
> `get.v1.traders.by_trader_pubkey.pnl`.

Same shape as Get user PnL but keyed by trader PDA pubkey. Required
query: `resolution` (1m, 1d). Optional: startTime/endTime, limit
(default 1000, max 1440).

# Get trader market PnL

> Handles `GET /v1/traders/{trader_pubkey}/pnl/markets` via
> `get.v1.traders.by_trader_pubkey.pnl.markets`.

Per-market PnL series for one trader PDA. Required query: `resolution`
(1m, 5m, 15m, 1h, 4h, 1d). Optional: startTime/endTime, limit (default
1000, max 1000 per market), symbols (comma-separated filter, default
all). Returns TraderMarketPnLSeries[]: marketId, symbol, tickSize,
baseDecimals, points[] (realizedPnl, cumulativePnl, cumulativeFundingPayment,
totalTakerFee, cumulativeTakerFee, unrealizedPnl, baseLots,
virtualQuoteLots, markPrice).

# Create wallet transaction challenge

> Handles `POST /v1/auth/wallet/transaction-challenge` via
> `post.v1.auth.wallet.transaction_challenge`.

Starts wallet login. Request: { wallet_pubkey }. Returns { nonce_id,
unsigned_transaction (base64 legacy tx, single Memo instruction —
wallets may prepend ComputeBudget/Lighthouse ixns but must preserve
the Memo ix, blockhash, and signer slot; never submitted on-chain),
expires_at (RFC3339) }. Echo nonce_id on the subsequent login call.

# Get wallet login nonce

> Handles `GET /v1/auth/nonce` via `get.v1.auth.nonce`.

Query: wallet_pubkey. Returns { nonce_id, message, expires_at } — the
message/nonce login variant of the auth flow.
