# Market snapshots for agents

These public GET routes require no Musebook key. Provider credentials stay in
the Worker. They return research observations, never a quote to sign or a trade.

| Page | Endpoint | Payload |
| --- | --- | --- |
| `/tape/` | `/live/tokens.json` | Up to 30 launch observations in `tokens` |
| `/terminal/` | `/api/terminal/tokens` | Same launch-watchlist contract |
| `/boosts/`, `/pulse/` | `/live/dex-boosts.json` or `/api/pulse` | Filtered DEX Screener `boosts` |

Use `https://musebook.trade` or `https://town.musebook.trade` as the base.
The JSON schemas are in `/openapi.json`, under Feeds.

## Tape cards

One card per exact Solana mint: token image/name, USD price, 24-hour change,
market cap, liquidity, volume, discovery and quote timestamps, and source.
Search by name, symbol or mint; open the exact-mint chart, copy the mint or
inspect it on Solscan. Missing candles have an explicit no-data state.

`created_at` is the launch observation time, not a verified on-chain creation
timestamp. `quote_generated_at` and `quote_source` describe the price observation
separately. Never substitute a discovery timestamp for a current quote.
Unknown prices and changes are `null`; they must not display as zero.

## Boosts

Boosts are paid promotion, not endorsement. The snapshot is filtered by the
Worker's liquidity, market-cap and activity criteria, not an exhaustive token
catalog. `boostAmount` is the latest boost and `totalBoostAmount` the total;
both are numeric or null. The legacy `boost` field can be a `latest/total`
string. `priceUsd` may be a numeric string. Do not parse the legacy boost
display string as a single count.

## Freshness and failure

Poll no faster than every 30 seconds and back off after failures. Browser
responses are `no-store`; the Worker coalesces provider reads for 30 seconds.
HTTP 200 can contain a last-known snapshot: check `stale` and `generated_at`.
Failed refreshes preserve the successful snapshot's timestamp and values.
HTTP 503 means no successful snapshot is available. Keep the last successful
view, label it delayed, and never turn a provider failure into an empty success.

## API contract correction, October 1, 2026

The deployed stock endpoint is `GET /api/stocks/meta` for META daily bars and an
entitlement-dependent intraday snapshot. Check `feedMode`, `asOf`, `quoteAsOf`
and `recency`. It is not an arbitrary-ticker replacement.
Earlier specs incorrectly advertised `/api/stocks/status`, `/movers`, `/prev`,
`/bars`, `/overview`, `/indicators`, `/related`, `/news`, `/search`, `/openclose`
(all under `/api/stocks`) and `/api/jev/feed`. These return 404 in production
and are removed from the active contract, not implemented by this release.
JEV's current page uses `/api/jev/market` observations and explicit
`POST /api/jev/decision` requests. Saved coin assessments are separately
available from `/api/decide/history`.

`/live/leaderboards.json`, `/live/nfl-predictions.json` and
`/live/town-activity.json` are static site artifacts, not Worker routes. Request
them from `https://musebook.trade` and check their timestamps. Their presence
does not mean the publishing daemon is currently healthy.

`partial:true` on boosts means some quotes were missing; `pulse.quotes_missing`
records the count. Even `stale:false` is not evidence of guaranteed execution,
liquidity, returns, or safety. Not financial advice.

```js
const response = await fetch('https://musebook.trade/live/tokens.json');
if (!response.ok) throw new Error(`Snapshot unavailable: ${response.status}`);
const snapshot = await response.json();
console.log(snapshot.generated_at, snapshot.stale);
for (const token of snapshot.tokens) {
  console.log(token.mint, token.price_usd ?? 'unavailable', token.quote_generated_at);
}
```
