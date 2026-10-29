---
name: "openmarket"
description: "Use OpenMarket when the user asks for OpenMarket, openmarket.xyz, or its unified cross-exchange crypto data API (OHLCV candles, open interest, funding rates, liquidations, orderbook heatmaps, volume profiles, TPO market profiles, real-time trade streams)."
---

# OpenMarket (openmarket.xyz)

Unified cross-exchange crypto data API: one endpoint, one schema, every data
type. Authenticated with the user-connected `custom.openmarket` credential
(`X-OpenMarket-Key` header via authd surrogate).

## Purpose
Use OpenMarket when the user asks for cross-exchange market data, or when a
chart datafeed needs candles / volume / funding / liquidations / orderbook
depth on crypto venues (Binance Futures, Bybit, OKX/OKEX_SWAP, Hyperliquid,
etc.).

## Tooling
Service-specific CLIs live under `~/workspace/skills/openmarket/bin/`.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py`
and call `add_surrogate_to_request(...)` before authenticated requests (the key
rides the `X-OpenMarket-Key` header). They must send only `hsurr:*` values,
and only to the hosts below.

## Auth
The credential is stored once the user completes the connector setup; nothing
here collects one. Never ask the user to paste a raw key in chat, set a secret
environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the
key. Check that the credential was attached at all: a request built without
the helpers named under Tooling carries nothing, and that looks exactly like
a wrong key. Only once a request that did carry the credential is still
rejected, call `credentials.request_api_access` with `reconnect` to replace
it. The connector is stored as `custom.openmarket`.

## Operating Rules
1. Use this skill when the user asks for OpenMarket, openmarket.xyz, or
   cross-exchange crypto data via this provider's API.
2. Restrict authenticated requests to: `api.openmarket.xyz`
   (REST) and `ap-sin3.ws.api.openmarket.xyz` (WebSocket trade stream).
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking
   for a key.

## CLI
`bin/openmarket.py GET <PATH> [--param name=value] ...` — attaches the stored
`custom.openmarket` credential as the `X-OpenMarket-Key` header via authd
surrogate exchange. `--param` may repeat (e.g. multiple `exchange=`).

```bash
# BTC hourly candles, Binance Futures
bin/openmarket.py GET /v1/points \
  --param type=TRADE_SIDE_AGNOSTIC_AGG \
  --param exchange=BINANCE_FUTURES \
  --param rawSymbol=BTCUSDT \
  --param interval=HOUR \
  --param from=1774800000 \
  --param period=3600

# BTC volume summed across Binance + Bybit + OKX, USD-normalized
bin/openmarket.py GET /v1/points \
  --param type=TRADE_SIDE_AGNOSTIC_AGG \
  --param exchange=BINANCE_FUTURES \
  --param exchange=BYBIT \
  --param exchange=OKEX_SWAP \
  --param coin=BTC \
  --param interval=HOUR \
  --param from=1774800000 \
  --param period=86400 \
  --param transform.groupBy.type=GROUP_BY_TYPE_SUM \
  --param transform.normalize.quote=USD

# Funding rates
bin/openmarket.py GET /v1/points \
  --param type=FUNDING_RATE_AGG \
  --param exchange=BINANCE_FUTURES \
  --param rawSymbol=BTCUSDT \
  --param interval=HOUR \
  --param period=86400

# Liquidation heatmap by price (Hyperliquid)
bin/openmarket.py GET /v1/points \
  --param type=HYPERLIQUID_LIQUIDATION_AGG \
  --param coin=BTC \
  --param interval=HOUR \
  --param period=3600 \
  --param transform.normalize.quote=USD
```

## Endpoint catalog (verified against provider docs 2026-09-29)
Base: `https://api.openmarket.xyz`. Everything goes through `GET /v1/points`;
the `type` parameter selects the dataset.

| Change `type` to... | And you get |
|---|---|
| `TRADE_SIDE_AGNOSTIC_AGG` | OHLCV candles |
| `OPEN_INTEREST_AGG` | Open interest across exchanges |
| `FUNDING_RATE_AGG` | Funding rates with predicted values |
| `LIQUIDATION_AGG` | Liquidation volume by side |
| `VOLUME_PROFILE_AGG` | Volume at each price level |
| `TPO_AGG` | Market Profile / Time Price Opportunity (exclusive) |
| `BLOCK_BOOK_SNAPSHOT_AGG` | Orderbook depth heatmap (up to 1,000 levels, `blockSize`, `maxDepth`, `sortDirection`) |
| `HYPERLIQUID_LIQUIDATION_AGG` | Liquidation heatmap by price |
| `HYPERLIQUID_TRIGGER_LIQUIDITY_AGG` | TP/SL trigger heatmap |

Common params: `exchange` (repeatable: BINANCE_FUTURES, BYBIT, OKEX_SWAP,
HYPERLIQUID_FUTURES...), `rawSymbol` (e.g. BTCUSDT), `coin` (e.g. BTC),
`interval` (MINUTE, HOUR, DAY), `from` (unix seconds), `period` (seconds),
`transform.groupBy.type=GROUP_BY_TYPE_SUM`, `transform.normalize.quote=USD`,
`tpoSession=TPO_SESSION_DAILY`, `tpoBlockSizeMinutes=30`.

## Real-time trade stream (WebSocket)
`wss://ap-sin3.ws.api.openmarket.xyz/nonbook/ws?encoding=json`
1. Connect. 2. Authenticate: `{"method":"public/authenticate","params":{"token":"<key>"}}`
3. Subscribe: `{"jsonrpc":"2.0","id":0,"method":"public/subscribe","params":{"channels":[{"type":"TRADE","exchange":"BINANCE_FUTURES","symbol":"BTCUSDT","category":"*"}],"compression":"brotli","version":"v2"}}`

## Related
- OpenMarket also runs a chart-control MCP server (`https://mcp.openmarket.xyz/`,
  Streamable HTTP + OAuth). It is a separate connection: the user signs in once
  in their browser, or mints an agent token at
  `https://openmarket.xyz/chart/console/agents`. Scopes: `mcp:read`,
  `mcp:chart`, `mcp:trade`, `mcp:alerts`. This skill does not manage that
  connection.
- For the site's charting upgrade goal, OpenMarket is the planned datafeed for
  cross-exchange data; BirdEye remains the OHLCV source for Solana tokens.
