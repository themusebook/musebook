# Phoenix Eternal public API — exchange endpoints

Source: https://docs.phoenix.trade (OpenAPI phoenix-public-api.json).
Base: https://perp-api.phoenix.trade
Pasted into the skill 2026-09-18.

## Documentation Index
Fetch the complete documentation index at: https://docs.phoenix.trade/llms.txt
Use this file to discover all available pages before exploring further.

# Get exchange

> Handles `GET /v1/view/exchange` via `get.v1.view.exchange`.

Returns the full exchange configuration: keys (globalConfig, authorities,
canonicalMint, globalVault, perpAssetMap, globalTraderIndex,
activeTraderBuffer, withdrawQueue) and static per-market configs. Does NOT
include live data like mark prices or current open interest.

# Get exchange keys

> Handles `GET /v1/view/exchange/keys` via `get.v1.view.exchange.keys`.

Returns exchange pubkeys (ExchangeKeysView).

# List markets

> Handles `GET /v1/view/exchange/markets` via `get.v1.view.exchange.markets`.

Returns an array of ExchangeMarketConfig: symbol, assetId, marketStatus
(uninitialized|active|postOnly|paused|closed|tombstoned), marketPubkey,
splinePubkey, tickSize, baseLotsDecimals, takerFee, makerFee,
leverageTiers (maxLeverage, maxSizeBaseLots, limitOrderRiskFactor),
riskFactors (maintenance/backstop/highRisk/upnl/upnlForWithdrawals/cancelOrder,
as percentages and bps), fundingIntervalSeconds, fundingPeriodSeconds,
maxFundingRatePerInterval, openInterestCapBaseLots,
maxLiquidationSizeBaseLots, isolatedOnly, optional commodityMetadata,
metadata (coinGeckoId, logoUri, calendar), optional statsSnapshot.

# Get market

> Handles `GET /v1/view/exchange/market/{symbol}` via `get.v1.view.exchange.market.by_symbol`.

Single ExchangeMarketConfig for a symbol (e.g. SOL-PERP). 404 if unknown.

# Get exchange snapshot

> Handles `GET /v1/exchange/snapshot` via `get.v1.exchange.snapshot`.

ExchangeSnapshotView: version, slot, slotIndex, exchange state
(ExchangeStateSnapshot: programId, globalConfig, authorities,
canonicalMint, usdcMint, globalVault, perpAssetMap, globalTraderIndex,
activeTraderBuffer, withdrawQueue, exchangeStatusBits/Features, active,
gated, withdrawalsAvailable) plus per-market ExchangeMarketSnapshot
entries (adds fundingConfig, markPriceParameters, isolatedOnly).

# Get exchange status

> Handles `GET /v1/view/exchange/status` via `get.v1.view.exchange.status`.

ExchangeStatusView: active (accepting orders), gated (restricted access),
withdrawalsAvailable.

# Submit register trader transaction

> `POST /v1/exchange/send-register-ixs`

Validates a base64-encoded transaction for the default trader account,
signs it with the Phoenix onboarder, simulates it to ensure the onboarder
pays no lamports, sends it to Phoenix's RPC, and returns the transaction
signature. Request: { transaction, traderAuthority, txFeePayer,
maxPositions?, traderPdaIndex?, traderSubaccountIndex? }.
Response: { signature, traderPda, traderOnboarder, txFeePayer,
maxPositions, includeRegisterTrader }.

# Build register trader instructions

> `POST /v1/exchange/build-register-ixs`

Returns the register and delegated-onboarding instructions for the default
trader account without a referral code. The caller chooses the transaction
fee payer, builds the transaction locally, and signs it with the trader
authority and fee payer. Request: { traderAuthority, txFeePayer,
maxPositions? }. Response: { instructions[] (programId, keys[],
data[]), traderPda, traderOnboarder, txFeePayer, maxPositions,
includeRegisterTrader }.

# Get orderbook

> Handles `GET /v1/view/orderbook/{symbol}` via `get.v1.view.orderbook.by_symbol`.

Query params: include_splines (bool), bypass_execution_band (bool, for
commodities after-hours). Returns OrderbookView: slot, symbol, bids/asks
as (price, size) pairs, mid, optional splines.

# Get mark price

> Handles `GET /v1/market/{symbol}/mark-price` via `get.v1.market.by_symbol.mark_price`.

Returns MarkPriceResponse: slot, slotIndex, symbol, markPrice { price, slot }.

# Get market stats history

> Handles `GET /v1/market/{symbol}/stats` via `get.v1.market.by_symbol.stats`.

Query params: start_time, end_time (ISO 8601, default last 1h → now),
limit (max 10000, default 1000), timeframe (1s, 5s, 1m, 5m, 15m, 30m,
1h, 4h, 1d). Returns MarketStatsHistoryResponse: market_id, symbol,
timeframe, stats[] of MarketStatsPoint { timestamp, slot, open_interest,
mark_price, spot_price, total_maker_fees?, total_taker_fees? }.
