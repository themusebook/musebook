---
name: dexscreener
description: "DEX Screener realtime data feed via the free public API and WebSocket streams. Search tokens, get pair/token market data (price, mcap, liquidity, volume, txns), boosted tokens, token profiles, community takeovers, paid orders, and trending metas. Triggers: dex screener, dexscreener, token boosts, realtime token feed, trending tokens, token profiles, pair data."
---

# DEX Screener

Realtime DEX market data via the free public DEX Screener API. **No API key, no connector credential needed** — the API is open at 60 requests/minute. This skill is the always-on feed: REST for lookups, WebSocket for live streams.

- REST base: `https://api.dexscreener.com`
- WS base: `wss://api.dexscreener.com`
- Chain ids: `solana`, `ethereum`, `bsc`, `base`, `arbitrum`, etc.
- Transport rules: Python shells out to `curl` (the egress proxy truncates large `urllib` responses with IncompleteRead; curl handles them); Node WS uses `ws` + `https-proxy-agent` with an `Origin` header (the DexScreener WS drops headerless connects — verified live).

## REST — bin/dex.py

```
dex.py search <query>                          # full-text token/pair search
dex.py tokens <chain> <addr[,addr...]>         # pair data for up to 30 token addresses
dex.py pairs <chain> <pairId>                  # one pair by pair address
dex.py token-pairs <chain> <tokenAddress>      # every pair for a token
dex.py boosts [latest|top]                     # boosted tokens
dex.py profiles [latest|updates]               # token profiles (paid listings)
dex.py takeovers                               # latest community takeovers
dex.py orders <chain> <tokenAddress>           # paid orders (boost/ads) on a token
dex.py metas [trending|<slug>]                 # trending metas or one meta's top pairs
```

Options: `--json` (raw JSON), `--limit N` (default 10 rows).

Pair rows carry: symbol, chain, dex, priceUsd, marketCap, liquidity USD, h24 volume, h24 price change, h24 buys/sells, token address, dexscreener URL.

Examples:
```
dex.py tokens solana 8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump
dex.py search "CLAWD"
dex.py boosts top --limit 5
dex.py tokens solana 8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump --json | jq '.[] | select(.chainId=="solana")'
dex.py metas trending
```

## Realtime WebSocket — bin/dex_stream.mjs

```
node dex_stream.mjs [--channel NAME] [--seconds N] [--limit N] [--chain solana] [--raw]
```

Channels: `boosts-latest` | `boosts-top` | `profiles-latest` | `profiles-updates` | `takeovers` | `ads`

One compact JSON object per stdout line: `{event, channel, chainId, tokenAddress, url, description, icon, boost?, claimDate?, links?}`. `event` is `snapshot` (initial handshake batch) or `update` (live arrival). Status/errors on stderr. Exit code 3 if the socket dies before any message (fails closed).

Examples:
```
node dex_stream.mjs --channel boosts-latest --seconds 60 --chain solana
node dex_stream.mjs --channel profiles-latest --seconds 120 --limit 20 --raw
```

## Feed notes

- Boosts = tokens teams paid to promote; strong new-launch signal but **paid placement ≠ quality** — always pair with pair data (liquidity, holder concentration) before acting.
- Profiles-latest streams paid token profile listings in realtime; takeovers stream community-claimed tokens.
- For price/mcap/volume on anything from the stream, follow up with `dex.py tokens <chain> <address>`.
- Keep REST under 60 req/min; prefer one WS connection per channel over polling.

## Related

- `dex-screener-scanner` skill: browser-automation scraping of dexscreener.com UI (heavier; use this API skill first).
- `pumpfun-live` skill: realtime pump.fun launch stream (launch events, not DEX market data).
- `solana-tracker` skill: alternative token data provider (needs API key).
