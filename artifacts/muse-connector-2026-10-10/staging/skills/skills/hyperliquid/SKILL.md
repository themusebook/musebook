---
name: "hyperliquid"
description: "Read-only Hyperliquid perps market data via Hyperliquid's keyless public API. Use when the user asks for Hyperliquid perps data: open interest, funding, mark prices, order books, candles."
---

# Hyperliquid (keyless public API)

Read-only perps market data from Hyperliquid. **No API key, no wallet, no signing.**
Plain HTTPS POST to `https://api.hyperliquid.xyz/info` with
`Content-Type: application/json`.

## What it replaces

Birdeye's `/perps/v1/*` Hyperliquid endpoints are not on the connected
Birdeye plan (401 "insufficient permissions", verified 2026-09-17). This is the
approved replacement path for open interest, per-coin overview, funding, and
book/candle data.

## CLI

`bin/hl_info.py <command> [args] [--json]`

| Command | What it returns |
|---|---|
| `overview [COINS...]` | Per-coin: mark px, oracle px, mid px, open interest (units + notional), funding, prev-day px, 24h notional volume |
| `oi [--limit N]` | Open interest leaderboard across all perp coins, ranked by notional OI (default top 20) |
| `funding [COINS...]` | Current + next predicted Hyperliquid-perp funding per coin |
| `mids` | All coin mark prices |
| `l2book COIN [--depth N]` | L2 book snapshot (up to 20 levels/side) |
| `candles COIN INTERVAL [--hours N]` | OHLCV candles (intervals: 1m 3m 5m 15m 30m 1h 2h 4h 8h 12h 1d 3d 1w 1M) |

Examples:

```bash
bin/hl_info.py overview BTC ETH SOL
bin/hl_info.py oi --limit 10
bin/hl_info.py funding --json
bin/hl_info.py candles BTC 1h --hours 48
bin/hl_info.py l2book HYPE --depth 5
```

## Endpoint mapping

| Need | `POST /info` body |
|---|---|
| Coin metadata + per-coin contexts (OI, funding, mark px, volume) | `{"type":"metaAndAssetCtxs"}` |
| Predicted funding rates per coin | `{"type":"predictedFundings"}` |
| All mark prices | `{"type":"allMids"}` |
| L2 book for one coin | `{"type":"l2Book","coin":"BTC"}` |
| Candle snapshot | `{"type":"candleSnapshot","req":{"coin":"BTC","interval":"1h","startTime":...,"endTime":...}}` |

## Known data gaps (document honestly, do not fake)

- **No liquidation-level / liquidation-map endpoint.** Hyperliquid exposes no
  aggregate long/short positions or liquidation heatmap. Depth from `l2Book`
  is not liquidation data — never present it as such.
- **No per-coin long/short ratio or aggregate open-position skew.** This was
  Birdeye's `/perps/v1/token/open_positions` niche; there is no keyless
  Hyperliquid equivalent. Per-user positions require a wallet address
  (`clearinghouseState`) and are not part of this skill.
- OI is returned in **coin units**; multiply by mark price for notional.

## Constraints

- Read-only market data only. No trading, no signing, no wallet authority.
- Never broaden this into positions on a specific account — that needs a
  user's address and is out of scope.
