# BirdEye connector — Muse submission dossier (2026-09-19)

## API connector: custom.birdeye (live, verified 2026-09-19)

BirdEye market data inside Muse. Connects the user's BirdEye API key so
agents can query Solana token data natively.

- **Connector slug:** `custom.birdeye`
- **Name:** BirdEye
- **Auth scheme:** API key → `X-API-KEY` request header
- **Allowed host:** `public-api.birdeye.so` only
- **Chain header:** `x-chain: solana` (per request)
- **Key storage:** Secure Vault via authd surrogate exchange. The raw key is
  never printed, logged, or persisted. The CLI sends only `hsurr:*`
  surrogate values.
- **Companion skill:** `birdeye` — documents setup and provides
  `bin/birdeye.py`, a generic authenticated caller:
  `birdeye.py GET <PATH> --header 'x-chain: solana'`

### Endpoint coverage (verified live 2026-09-19)

| Endpoint | Status on connected key |
|---|---|
| `GET /defi/networks` | ✅ |
| `GET /defi/token_overview?address=` | ✅ (30m tape: trades/buys/sells, USD volumes, price change, wallets, holders) |
| `GET /defi/v3/token/meme/list` | ✅ |
| `GET /defi/v3/token/meme/detail/single?address=` | ✅ (meme_info: created_at, creator, progress_percent, graduated) |
| `GET /defi/token_trending` | ✅ |
| `GET /defi/v3/token/market-data?address=` | ✅ (price, mcap, fdv, liquidity, holders, supply) |
| `GET /defi/v3/price/stats/single?address=&list_timeframe=24h` | ✅ (24h price/change/high/low) |
| `GET /defi/v3/pair/overview/single?address=` | ✅ (pair + base/quote) |
| `GET /defi/v3/search?keyword=` | ✅ |
| `GET /defi/v3/ohlcv?address=&type=1m` | ✅ (may be empty for illiquid mints) |
| `GET /defi/token_security` | ❌ 401 on this plan |
| `GET /defi/token_creation_info` | ❌ 401 on this plan |
| `GET /defi/v3/token/meta-data/single` | ❌ 401 on this plan |
| `GET /defi/v3/token/fee/single`, `/multiple` | ❌ 401 on this plan |
| `GET /market/v1/blockchain-metrics` | ❌ 401 on this plan |
| `GET /smart-money/v1/token/list` | ❌ 401 on this plan |
| `GET /wallet/v2/pnl/*`, `/wallet/v2/balance-change`, `/wallet/v2/token-balance` | untested — needs a wallet address |

### Rate limits
Pace calls (~1.2s apart) with backoff on 429. Prefer one `token_overview`
call per mint.

### Form copy

**Tagline:**
Solana market data inside Muse — live prices, trending tokens, and the 30m tape via BirdEye

**Description:**
BirdEye brings live Solana market data to Muse through your own API key.
Connect it here and your agent can pull token prices, market caps, liquidity,
holder counts, 24h trending, new meme launches, pair overviews, and the 30m
trade tape (buys/sells, volumes, wallets) — all read-only. The key is stored
in your Secure Vault and never exposed. Data is research only, not financial
advice.

**Example prompts:**
- "What's the 24h trend on Solana right now?" (token_trending)
- "Show me $CLAWD's market data: price, mcap, liquidity, holders" (market-data)
- "What are the newest pump.fun launches with the most 30m volume?" (meme/list + token_overview)
