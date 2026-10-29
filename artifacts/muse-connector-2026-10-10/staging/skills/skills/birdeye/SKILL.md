---
name: "birdeye"
description: "Use BirdEye when the user asks for BirdEye or this provider's API."
---

# BirdEye

## Purpose
Use BirdEye with the user-connected `custom.birdeye` credential.

## Tooling
Add service-specific CLIs under `~/workspace/skills/birdeye/bin/`.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and call `add_surrogate_to_request(...)` before authenticated requests. They must send only `hsurr:*` values, and only to the hosts below.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.birdeye`.

## Operating Rules
1. Use this skill when the user asks for BirdEye or this provider's API.
2. Restrict authenticated requests to: public-api.birdeye.so.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.

## CLI
`bin/birdeye.py GET <PATH> [--header 'Name: Value'] ...` — attaches the stored
`custom.birdeye` credential as `X-API-KEY` via authd surrogate exchange.

```bash
bin/birdeye.py GET '/defi/price?address=So11111111111111111111111111111111111111112' --header 'x-chain: solana'
bin/birdeye.py GET '/perps/v1/token/list?time_frame=all&sort_by=open_interest&sort_type=desc&limit=10' --header 'x-perp: hyperliquid'
```

## Endpoint catalog (Birdeye MCP / REST)
Every endpoint is directly callable as REST at `https://public-api.birdeye.so`.
Match the task to the right endpoint before calling. Most `defi` endpoints take
an `address` query param and an `x-chain` header (e.g. `x-chain: solana`).

| Need | Endpoint |
|---|---|
| Supported networks | `GET /defi/networks` |
| Current token price | `GET /defi/price?address=<mint>` |
| Historical price (line) | `GET /defi/history_price?address=<mint>&address_type=token&type=<interval>` |
| OHLCV candles (token) | `GET /defi/v3/ohlcv?address=<mint>&type=<interval>` |
| Token stats / overview | `GET /defi/token_overview?address=<mint>` |
| Token trades (v3) | `GET /defi/v3/token/txs?address=<mint>` |
| Trending tokens | `GET /defi/token_trending` |
| Meme token list | `GET /defi/v3/token/meme/list` |
| Smart money token list | `GET /smart-money/v1/token/list` |
| Token security / risk | `GET /defi/token_security?address=<mint>` |
| Holder distribution | `GET /holder/v1/distribution?address=<mint>` |
| Token transfer list | `POST /token/v1/transfer` |
| Wallet current net worth | `GET /wallet/v2/current-net-worth?wallet=<addr>` |
| Wallet net worth chart | `GET /wallet/v2/net-worth?wallet=<addr>` |
| Wallet PnL summary | `GET /wallet/v2/pnl/summary?wallet=<addr>` |
| Wallet tx history (beta) | `GET /v1/wallet/tx_list?wallet=<addr>` |
| Search (token / market) | `GET /defi/v3/search?keyword=<q>` |
| Perps token list | `GET /perps/v1/token/list` (header `x-perp: hyperliquid`) |
| Token market data (price/mcap/fdv/liq/holders/supply) | `GET /defi/v3/token/market-data?address=<mint>&ui_amount_mode=scaled` |
| Price stats (needs `list_timeframe`, e.g. `24h`) | `GET /defi/v3/price/stats/single?address=<mint>&list_timeframe=24h&ui_amount_mode=raw` |
| Pair overview (needs pair address) | `GET /defi/v3/pair/overview/single?address=<pair>&ui_amount_mode=scaled` |

## Endpoints that 401 on this plan (do not retry-loop)
`token_security`, `token_creation_info`, `token/meta-data/single`,
`token/fee/single`, `token/fee/multiple`, `market/v1/blockchain-metrics`,
`smart-money/v1/token/list`. Mark the field unavailable.

## Wallet endpoints (need a wallet address)
`wallet/v2/pnl/summary`, `wallet/v2/pnl/details`, `wallet/v2/pnl`,
`wallet/v2/pnl/multiple`, `wallet/v2/balance-change`,
`wallet/v2/token-balance`, `wallet/v2/current-net-worth`, `wallet/v2/net-worth`
— pass `?wallet=<addr>`. Untested until a wallet is supplied.
| Perps token overview | `GET /perps/v1/token/overview` (header `x-perp: hyperliquid`) |
| Perps open positions | `GET /perps/v1/token/open_positions` (header `x-perp: hyperliquid`) |
| Perps liquidation map | `GET /perps/v1/token/liquidation_map` (header `x-perp: hyperliquid`) |

## Known plan limits (verified 2026-09-17)
- The connected key returns **401 "insufficient permissions"** on all four
  `/perps/v1/*` endpoints — perps are not on this plan. Do not retry-loop them;
  use Hyperliquid's free public API for perps data instead. Skill:
  `~/workspace/skills/hyperliquid/` (`bin/hl_info.py`) — keyless POST to
  `https://api.hyperliquid.xyz/info`. Known gaps there: no liquidation-map
  endpoint and no aggregate long/short data; see
  `~/workspace/goals/perps-market-data-wiring/agent_notes/2026-09-18-hyperliquid-switch.md`.
- Watch the credit budget: CU cost per call was not published; keep calls
  minimal and prefer the cheapest endpoint that answers the question.
