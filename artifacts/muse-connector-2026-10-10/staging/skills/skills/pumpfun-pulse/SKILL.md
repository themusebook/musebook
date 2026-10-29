---
name: "pumpfun_pulse"
description: "Run the 15-minute PumpFun Pulse: collect recent pump.fun launches, enrich via BirdEye, score and rank them. Use when the user asks for the pulse, the best/new launches, or trending pump.fun tokens."
---

# PumpFun Pulse

## Purpose
Every 15 minutes, surface the strongest recent pump.fun launches as a ranked
research digest, plus a 24h trending block. This is market research, not
investment advice: present data and let the user decide.

## Tooling
- Collector/scorer: `~/workspace/skills/pumpfun-pulse/bin/pulse.py`
- Enrichment + trending: `~/workspace/skills/birdeye/bin/birdeye.py` (BirdEye REST)
- Launch discovery (primary, no API calls): the launch logger's
  `~/workspace/goals/pump-fun-launch-pulse/hidden_files/all_launches.jsonl`
  (real creation timestamps, live stream)

Run:
```
python3 ~/workspace/skills/pumpfun-pulse/bin/pulse.py [--window-min 20] [--max-enrich 12] [--top 10] --json-only
```
`--json-only` prints a single JSON object for cron workers.
`--build-live OUT_JSON --live-count 12` refreshes the Musebook live-tokens JSON.

## Auth
BirdEye credential is stored as `custom.birdeye` and attached via surrogate
exchange inside `birdeye.py` (header `X-API-KEY`, host `public-api.birdeye.so`).
Never ask for a raw key. On 429s the script backs off; on repeated failures
report rather than loop.

## BirdEye endpoints used

| endpoint | used for |
|---|---|
| `GET /defi/token_overview?address=` | 30m tape: trade30m/buy30m/sell30m, vBuy30mUSD/vSell30mUSD, priceChange30mPercent, uniqueWallet30m, holder, mcap, liquidity |
| `GET /defi/v3/token/meme/detail/single?address=` | name/symbol, extensions (socials), meme_info: created_at, creator, progress_percent, graduated |
| `GET /defi/token_trending?sort_by=rank&interval=24h&sort_type=asc&limit=10` | 24h trending block in the digest and tweets |
| `GET /defi/v3/token/meme/list?sort_by=last_trade_unix_time&sort_type=desc` | fallback discovery when the launch log is missing/stale |
| `GET /defi/v3/ohlcv?address=&type=1m` | sparkline data for `--build-live` (may be empty; degrades to no sparkline) |

Tape window is **30m** — BirdEye has no 15m bucket, so 30m is used honestly
instead of interpolating. Digest fields use `volume_30m`, `price_change_30m_pct`, etc.

## Not available on this BirdEye plan
- `GET /defi/token_security` → 401 insufficient permissions
- `GET /defi/token_creation_info` → 401 insufficient permissions

Authority/rug fields are therefore unavailable in the pulse. Pre-trade
authority diligence stays with the rug-check skill. Graduated tokens are
flagged (`graduated`, trades on AMM not the curve).

## Operating Rules
1. The digest ranks by a transparent momentum score (30m volume, txns,
   holders, buy pressure, socials, near-graduation progress) minus penalties
   (negative 30m move, graduated flag).
2. Always show score reasons and flags next to each pick.
3. Include mint links (pump.fun, Solscan, BirdEye) for every ranked token.
4. Label the generation time and tape window; data older than the window is stale.
5. Never frame ranked tokens as buy recommendations. It is a watchlist.
6. Never trade from the pulse. Trading is a separate, per-trade user approval.
