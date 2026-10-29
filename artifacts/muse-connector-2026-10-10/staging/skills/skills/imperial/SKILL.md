---
name: imperial
description: Entry-point skill for Imperial perpetual routing on Solana. Use before answering or acting on Imperial router flows, Phoenix-routed perps, profile funding, market/portfolio intel, risk checks, TP/SL, TWAP, grid, Imperial Touch binaries, Armada, or Telegram bot trading workflows.
---

# Imperial

Imperial is a perpetual futures router on Solana — a single passthrough program
that brokers trades across multiple underlying perp venues (Jupiter, Phoenix,
GMTrade, …). This HTTP API is the surface third-party bots and integrators use
to authenticate, submit orders, and read public on-chain state.

Base: `https://api.imperial.space` · OpenAPI 3.1.0 · full spec vendored at
`imperial-openapi.json` in this skill directory (62 paths, fetched 2026-09-22).
Scalar docs: `https://api.imperial.space/api/v1/docs`.

Core rules:

- Treat `IMPERIAL_JWT` as a trading credential. Never display, log, or commit it.
  Durable copy belongs in the Secure Vault (connector `custom.imperial`), never
  in files. Read it from the `IMPERIAL_JWT` env var at runtime.
- Treat every profile as isolated. Always track `profileIndex` (0–5).
- `POST /mobile/orders[/batch|/cancel|/collateral|/update]` returns HTTP 200 even
  on rejection — always inspect `success` / `error` / `errorCode` in the body.
- Prefer Phoenix (`underwriter=2`) unless the user explicitly requests another
  venue or route data says otherwise.
- For Telegram/webhook flows, only promise durable strategy execution when a
  real runner exists. Do not present a stateless webhook as a TWAP/grid engine.
- No orders, deposits, partner registration, or builder-code attachment without
  explicit per-action user approval.

Sub-skills: `imperial-trade-execution` (order placement), `imperial-portfolio-intel`
(balances/positions/orders), `imperial-risk-management` (pre-trade checks),
`imperial-twap-execution` (TWAP/DCA planning), `imperial-execution-modes` (mode taxonomy).

CLI: `bin/imperial.py` — auth helpers, public reads, JWT-gated trading calls.
`--confirm` required for any mutating call. JWT via `IMPERIAL_JWT` env or `--jwt`.

## Setup (2026-09-18, re-verified 2026-09-22)

- Operator wallet: `5rxgJXoN2xvoZHcLXav1pEHAhvygLziZsz3xAzNEJfgr` (user-supplied).
- Auth: user signs `imperial:mobile-connect:{wallet}:{nonce}` in their own wallet,
  exchanges the code themselves, hands over a fresh ~30-day JWT. Read-only calls
  confirmed working: `/mobile/balances`, `/mobile/points`,
  `/mobile/partner/registration`.
- Profiles: all six (0–5) exist; profile 0 PDA
  `9A81GVjHhasMXKdaURSRinzJUzFSdtowKFMTL634CjiF`. All unfunded (0 USDC) as of
  2026-09-18 — funding via `/deposit/build-tx` needs the user's wallet signature.
- Points: Season 1, 0 points. Partner: not registered (no partner code supplied;
  register before first order for the discounted fee tier).
- Convention: profileIndex 0 default; slippage 50 bps (user-supplied config).
- Market-data tweets use only the public endpoints (`/mark-prices`,
  `/funding-rates`); no JWT needed there.

## Authentication (JWT-gated trading)

1. `POST /api/v1/mobile/connect` — sign
   `imperial:mobile-connect:{wallet}:{nonce}` with the Solana keypair, post
   `{wallet, message, signature}`. `{nonce}` must be a **current Unix timestamp**
   (seconds or millis), not random: rejected if >5 min old or >60 s in the
   future, single-use. Response: one-time `code` (expires in 5 min, redeem once).
   - Delegate mode: message `imperial:delegate-connect:{wallet}:{delegate}:{nonce}`,
     signature by the delegate key, include `delegate` field.
   - Failure returns opaque 401 `{"error":"Failed to generate mobile session"}`
     for any cause — with a valid signature, an unexpected 401 almost always
     means the nonce is not a fresh timestamp. 400
     `{"error":"Invalid message format"}` means the signed string didn't match
     the prefix.
2. `POST /api/v1/mobile/exchange` — `{code}` → `{jwt, expiresAt}`.
3. Send trading requests with `Authorization: Bearer <jwt>`. The JWT's `wallet`
   claim must match the `wallet` field in every request body.
4. `POST /api/v1/mobile/revoke` — revoke on shutdown / key rotation.

The JWT is a Solana-signature-anchored delegation: holding it equals letting the
operator place orders from the wallet's profiles. Treat like an API key.
Multi-wallet bots: each wallet owner completes the flow and shares their JWT;
one request per wallet; any owner can revoke independently.

## Rate limits

600 req/min sustained, burst 120. Keyed per-wallet with a valid JWT, else per-IP.
429 returns `Retry-After` + `{"error":"rate_limited","retry_after_seconds":N}`.
`/health`, `/ws`, Telegram webhook are not rate-limited.

## Trading endpoints (JWT required unless noted)

- `POST /api/v1/deposit/build-tx` — `{wallet, profileIndex, mode, amount,
  deferOperatorSignature?}`. mode `deposit` credits USDC from the wallet's USDC
  ATA into the profile's USDC ATA; `withdraw` pulls back. Amount in USDC native
  units (6-decimal). Returns a sponsored, partially-signed tx — caller signs with
  the wallet keypair before submitting. `deferOperatorSignature: true` leaves the
  operator slot empty so the wallet signs first (avoids simulate warnings).
  Funding from native SOL is NOT supported — wrap to WSOL client-side. 400
  `WithdrawalBlockedByLoan` when a loan blocks egress.
- `GET /api/v1/mobile/balances` — per-subaccount USDC (6-decimal native units),
  profile_index 0–5. Uninitialized profiles return `usdc: 0` (normal, not a gate).
- `POST /api/v1/mobile/orders` — submit an order (see Order model below).
- `POST /api/v1/mobile/orders/batch` — `{entry (action=0), closeOrders[]}`:
  entry plus attached TP/SL/ratchet/DCA-close legs in one request. All legs
  carrying a builderCode must carry the same one.
- `POST /api/v1/mobile/orders/cancel` — `{wallet, profileIndex, orderPda,
  cascadeChildren?}`.
- `POST /api/v1/mobile/orders/collateral` — add/remove collateral
  (`action` 0/1). On a Phoenix cross seat, `marketMint`/`side` name any open
  market (transport only — the seat has one balance). Withdrawal cap is
  `effectiveCollateralForWithdrawalsUsd − initialMarginForWithdrawalsUsd`.
- `POST /api/v1/mobile/orders/preflight` — same body as `/mobile/orders`; asks
  whether the order would be accepted without placing it. Use before every live
  order.
- `POST /api/v1/mobile/orders/update` — `{wallet, profileIndex, orderPda}` plus
  any of `triggerPrice`, `sizeUsd`, `slippageBps`, `closeBps`, `priority`.
  Not supported for Phoenix-native maker orders (cancel + replace instead).
- `GET /api/v1/mobile/points` — wallet's Imperial points for the active season
  (credited weekly, not per-trade).
- `PUT /api/v1/passthrough/users/{wallet}/profiles/{index}/margin-mode` —
  `{"marginMode":"unified"|"isolated"}`. Accepts JWT or Solana signature via
  `x-pubkey`/`x-signature` headers over
  `imperial:margin-mode:{wallet}:{index}:{marginMode}`. Requires the profile to
  be named first (`PUT .../name` with signature over
  `imperial:profile-name:{wallet}:{index}`). Unified = Phoenix cross-margin seat.
- `POST /api/v1/passthrough/users/{wallet}/profiles/{index}/sync` — swap
  non-USDC residue (WSOL/WBTC/WETH from Jupiter long custody) back to USDC and
  route to the user wallet. Idempotent.
- `POST /api/v1/phoenix/register` — activate a wallet's Phoenix profile under
  Imperial's referral code. (Phoenix orders auto-activate the trader account on
  first use — calling this first is optional.)
- `POST /api/v1/mobile/partner/register` — `{code}` + wallet JWT. One-time per
  wallet, idempotent (retry on 503). Discounted fee tier + volume attribution.
  Register before the first order; a wallet binds to one partner code permanently.
- `GET /api/v1/mobile/partner/registration` — verify registration status.
- `GET /api/v1/mobile/builder/summary?code=` — accrued/paid/claimable builder
  fees. Code-as-credential, no JWT.

## Public reads (no auth)

Market/venue: `GET /mark-prices`, `/funding-rates`, `/route`,
`/phoenix/markets`, `/phoenix/mark-prices`, `/phoenix/depth`, `/phoenix/volumes`,
`/gmtrade/markets`, `/gmtrade/funding-rates`, `/gmtrade/liquidity`,
`/jupiter/pool-info` (cache-fronted), `/priority-fee`, `/close-slippage`,
`/status`.

Wallet-scoped (pass `walletAddress`): `/positions` (+`underwriter` filter),
`/orders`, `/order-history` (+`order_pda` detail route), `/trades`,
`/pnl-history` (`resolution` 1h|1d), `/funding-history`, `/deposit-history`,
`/phoenix/direct-positions` (independent of Imperial indexer),
`/phoenix/margin-account` (+`profileIndex`; null = never onboarded, not an error),
`/passthrough/users/{wallet}/profiles` (six subaccounts + margin modes),
`/passthrough/users/{wallet}/orders` (passthrough subset; `status`,
`profile_index`, `limit` filters), `/touch/positions`.

Platform stats: `/stats/summary`, `/stats/markets` (`period` 24h|7d|30d),
`/stats/volume`, `/stats/open-interest` (+`/history`), `/revenue/armada-balances`.

## Order model

`POST /mobile/orders` body — required: `wallet`, `profileIndex` (0–5),
`underwriter`, `side` (0=long, 1=short), `action` (0=Increase, 1=Decrease),
`orderType`, `fundingStatus` (0=funded at creation), `priority`,
`collateralAmount`, `sizeUsd` (6-decimal), `slippageBps`, `triggerPrice` (oracle
scale 1e9), `triggerCondition` (0=Above, 1=Below). Either `symbol` (canonical,
e.g. `SOL`, `XAU`) or `marketMint` must be set — `symbol` resolves server-side
per venue. Optional: `marketPrice` (per-underwriter scale, see below),
`builderCode`, `extraData`, `parentOrderPda`, `phoenixNative`, `closeBps`
(decrease only: fraction of the LIVE position, 10000 = full close; full close may
send `sizeUsd: 0` with closeBps omitted), `quote`/`quoteId` (Armada),
`requestedHedgeVenue` (Armada only).

Underwriters: 0 Jupiter, 2 Phoenix, 3 GMTrade, 5 Imperial Pairs, 6 Imperial
Touch, 7 Imperial Armada. (1/4 = Flash Trade / V2 — venue SHUT DOWN, rejected on
create, still on historical rows.)

Order types: 0 Market (triggerPrice ignored), 1 Limit, 2 StopLimit,
3 LandMine (`extraData.waitPrice`, `waitDuration`), 4 Ratchet / 6 RatchetEntry /
10 FibRatchet / 11 FibRatchetEntry (`extraData.worstPrice`, `ratchetSize`),
9 Dca (`dcaStartPrice`, `dcaEndPrice`, `dcaNumLegs`), 12 DcaClose, 13 DcaTimeClose,
14 DcaRatchetClose, 15 DcaTime, 16 DcaRatchet. Pairs (5) and Armada (7) reject
the DCA family. Touch (6) accepts only 0/1/2.

Price scales: `triggerPrice` and every price in `extraData` are ALWAYS oracle
scale (×1e9), every venue. `marketPrice` is per-underwriter: Jupiter/Phoenix/
Pairs/Armada = micro-USD (×1e6; SOL $64.94 → 64940000), GMTrade = oracle scale
(×1e9), Touch = ignored (send 0). Wrong scale fails (or vacuous-passes) the
on-chain slippage guard. On Armada, `marketPrice` also becomes the request's
`expected_price` for both on-chain price bands — send a live one, and Armada
opens require non-zero `slippageBps`.

Phoenix-native maker orders: set `phoenixNative: true` (only underwriter=2 with
orderType=1/action=0, or orderType=5 PrivateTpSl). Post-only, no slide; crossing
orders are rejected, not repriced. No in-place update (cancel + replace).
Partial fills supported; poll `/orders`/`/positions` or watch `/ws` — placement
is not the fill. Default (unset) keeps the keeper-managed IOC fallback.

Response convention: HTTP 200 even on rejection — inspect `success`, `error`,
`errorCode`. Machine codes: LeverageTooHigh/Low, SlippageExceeded,
MarketClosed, TradingPaused, PositionAlreadyClosed, MinCollateral,
ReduceBelowMinCollateral, InsufficientBalance/Margin/VenueBalance,
SwapRouteUnavailable, PostOnlyWouldCross, ProfileHasOpenPositions,
CancelViaAppOnly, LoanMarketNotWhitelisted, LoanVenueUnsupported,
LoanSizeAddBreaksFloor, VenueCapacity, VenuePriceFeedStale, VenueRejected,
TouchQuoteMoved, TouchBarrierSwept, TouchSettlesAtExpiry, Custom<N>, or
UnknownTradeFailure/InternalError. 4xx = malformed input/auth; 5xx = server/order-bot
transport failure.

Close legs: use `closeBps` against the LIVE position — never echo the open's
`sizeUsd` (oracle-price drift turns intended full closes into dust that the venue
rejects with MinCollateral).

## Subaccounts (profiles)

Six implicit subaccounts per wallet, index 0–5. No create call — the profile PDA
is created lazily by the order-bot on first `/deposit/build-tx` or first order
targeting that index. Balances and positions never mix across profiles.
Convention: profile 0 default, 1+ strategy buckets. `profileIndex` required on
every order, deposit, and balance call.

Cross margin (unified): per-profile, Phoenix-only. A unified profile routes new
positions onto Phoenix's cross-margin seat — one collateral balance backs every
market on it. On a cross seat, `collateralAmount` on an open is a top-up deposit,
not per-leg margin; admission is seat-wide
(`free + collateralAmount ≥ sizeUsd / maxLeverage`). Read seat state from
`GET /phoenix/margin-account` or the `phoenixCrossSeats[]` block on
`/positions` (positions and margin from the same instant). Per-position
liquidation fields are null on cross rows — use `liquidationPricesBySymbol`
(Phoenix-raw symbols, e.g. GOLD; null = unknown, never 0). Key local state on
`(positionPda, asset, side)` — `positionPda` is the shared trader account.
Unified rejects: non-Phoenix underwriters, lending-pool loans, `isolatedOnly`
markets.

## Imperial Touch (binary options, underwriter 6)

One-touch binaries, not perps: buy a fixed payout for an up-front premium.
Touch (side 0) pays full payout if spot reaches the barrier any time before
expiry; No-Touch (side 1) pays if it never does. Premium is the entire risk —
no liquidation, margin, funding, or collateral to reclaim.

- `GET /touch/markets` — every market with live spot, pricing config, vol state,
  book inventory. Each tenor is its own row (`marketId`); group by symbol prefix
  (`SOLTOUCH` → `SOL`). `halted: true` = not quoting. Always send `marketMint`
  (the market PDA), not bare symbol.
- `GET /touch/deals` — ranked quotable barriers at ±1/2/3/5/8% from spot with
  indicative `askBps` (premium = payout × askBps / 10000).
- Buy: `POST /mobile/orders` with `underwriter: 6, action: 0, orderType: 0`
  (Market; 1/2 rest until the barrier prints), `triggerPrice` = barrier (1e9),
  `sizeUsd` = payout (µUSD), `collateralAmount` = premium budget (max, µUSD;
  ≥1¢ per $1 payout), `slippageBps: 0`. Consent is a budget: the fill debits the
  live ask and refunds the difference; if the live ask exceeds budget nothing
  trades (`TouchQuoteMoved`).
- Sell back: same endpoint, `action: 1, orderType: 0`, `triggerPrice` =
  positionId + 1 (an ID, NOT 1e9-scaled), `sizeUsd` echoed byte-for-byte from
  `/touch/positions`, `collateralAmount` = min-refund floor (0 = any quotable bid).
  Unavailable after the barrier is swept or the cohort expired
  (`TouchSettlesAtExpiry` / `TouchBarrierSwept`) — then wait for settlement.
- Settlement is automatic (keeper per cohort). Poll `/touch/positions`:
  `open → settled` (`won` = outcome) or `bought_back`. Proceeds land in the
  profile's USDC. Touch positions appear ONLY on `/touch/positions` — absent
  from `/positions`, `/trades`, `/orders`, `/stats/*`, and both WS streams.

Expiry is cohort-quantized: open time snaps DOWN to `cohortQuantumSecs`, expiry
is one `cohortWindowSecs` later. An open in the final min(75s, window/4) joins
the NEXT cohort (forward start). Read `openTs`/`expiryTs` off the position.

## Imperial Armada (underwriter 7)

Off-Solana fills hedged on-venue; the user's `slippageBps` band is the entire
price bound (non-zero required on opens; closes exempt). `requestedHedgeVenue`:
0 = automatic (default), 1 = bind to Armada's current hedge route (2/3 reserved,
rejected; a binding route is never silently substituted). Reads:
`/armada/markets`, `/armada/quote` (server-authoritative; pass `wallet`,
`notionalUsd`, `asset`, `side`; `quoteId` binds the quote to the order),
`/armada/orderbook`, `/armada/open-availability` (advisory admission),
`/armada/fills`, `/armada/margin` (cross seat by default; `asset` for isolated),
`/armada/status`, `/armada/status.capital`, `/armada/treasury`,
`/revenue/armada-balances`.

## WebSockets (unauthenticated, unmetered)

`GET /ws` — wallet-scoped position/order stream. Subscribe replaces the whole
set: `{"type":"subscribe","wallet":"<pk>","positionState":true}` or
`{"type":"subscribe","wallets":["<pk1>","<pk2>"],"tradeEvents":true}`.
`positionState` pushes full position rows (~1/s re-mark while open; quiet while
flat); `tradeEvents` pushes typed settled close events (`position_closed` /
`position_liquidated`, dedupe by `lifecycleId`, at-least-once). Always-sent
triggers: `positions_updated`, `orders_updated`, `order_rejected`
(`actionId`, `reasonCode`). Caps: 200 wallets/connection; `positionState`
honored up to 25 wallets. `{"type":"ping"}` → `{"type":"pong"}`. No replay
buffer — re-subscribe on reconnect; the snapshot re-syncs.

`GET /ws/market` — public market data: `subscribe_funding_rates`,
`subscribe_mark_prices`, `subscribe_phoenix_depth` (optional `symbols` filter).
Pushes: `funding_rate_update` (sign convention: longRate > 0 = longs pay shorts;
Phoenix short = −long; Jupiter funding null, borrow ≥ 0), `mark_price_update`
(`venue: "index"`, source `pyth_lazer` = the number Imperial marks with),
`phoenix_depth_update` (Phoenix-raw symbols, e.g. GOLD). Each subscribe pushes
the current snapshot first.

## Builder codes & partner program

- Builders attach `builderCode` on `/mobile/orders` (or every leg of `/batch` —
  all legs same code or none). Fixed bps on the same base as the standard fee,
  both legs. Preview via `/trade-preview?...&builderCode=` (note: this path is
  documented but not in the vendored OpenAPI spec — verify before relying on it).
  `GET /mobile/builder/summary?code=` for accruals/payouts; code is the
  credential, no JWT. Disclose the fee to users in-app.
- Partners: auth → `POST /mobile/partner/register {"code"}` → discounted fee
  tier + volume attribution, one-time per wallet (first code wins). Verify with
  `GET /mobile/partner/registration`.

## Trading bot quickstart (per docs)

1. Auth (`/mobile/connect` → `/mobile/exchange`).
2. Fund: `/deposit/build-tx` (mode `deposit`), sign with the wallet keypair,
   submit. Size from `/route`'s `requiredDeposit` (pass `wallet`), not from cost
   breakdown expectations.
3. Pick venues: `/funding-rates` per-symbol per-venue rates; `/route` for
   single-venue cost-optimized recommendation.
4. Check `/mobile/balances`; open legs sequentially via `/mobile/orders`
   (`action=0`); if leg 2 fails, immediately `Decrease` leg 1. Inspect `success`
   on the HTTP-200 body. Resting orders return `orderPda` for cancel/update.
5. Track via both WS endpoints; close with `action=1` + `closeBps: 10000`
   (full) — never echo open `sizeUsd`.
6. Reclaim non-USDC residue via `/passthrough/.../sync`.

## Live-trading readiness checklist

- [ ] Fresh JWT in Secure Vault (`custom.imperial`), `expiresAt` in the future.
      User signs the connect message in their own wallet; code exchanged once.
- [ ] Partner code registered (discounted fees) — needs user-supplied code.
- [ ] Profile funded: `/deposit/build-tx` → user signs → submit → verify on
      `/mobile/balances`. Profiles currently unfunded (0 USDC).
- [ ] `preflight` green on the exact order body before every live order.
- [ ] Per-trade user approval of exact terms (side, venue, size, leverage,
      profile, slippage) — standing rule, no exceptions.
- [ ] WS subscriptions up (`/ws` + `/ws/market`) or a poll loop as fallback.
- [ ] Revoke JWT on shutdown / rotation via `/mobile/revoke`.
