# pumpfun-live

Live pump.fun token-launch stream, via the public Clawd relay WebSocket.
No account, API key, or login needed — the relay is a public stream.

## Endpoint

- WebSocket: `wss://clawd-ws.fly.dev/ws` (dashboard: `https://clawd-ws.fly.dev/`)
- The server requires an `Origin` header on the handshake (browser-like).
  Node's built-in WebSocket fails; use the bundled `ws` package with an
  `Origin: https://clawd-ws.fly.dev` header (see `listen.mjs`).

## Frame types (observed)

- `status` — heartbeat: `{type, connected, uptime, totalLaunches, githubLaunches, totalClaims, clients}`
- `token-launch` — one per new pump.fun mint:
  `{type, time, name, symbol, mint, creator, signature, metadataUri,
    imageUri, description, marketCapSol, website, twitter, telegram,
    isV2, hasGithub, githubUrls}`

Other types may appear; the listener passes unknown types through.

## Listener

`listen.mjs` prints one compact JSON object per line.

```
node listen.mjs [--seconds N] [--limit N] [--min-mcap SOL]
                [--has-twitter] [--match REGEX]
                [--types token-launch,status] [--raw]
```

Examples:

```bash
# watch launches for 60s
node listen.mjs --seconds 60

# launches mentioning clawd (name/symbol/description)
node listen.mjs --seconds 300 --match clawd

# only launches already at 50+ SOL mcap with a twitter link, first 10
node listen.mjs --min-mcap 50 --has-twitter --limit 10

# include relay heartbeats
node listen.mjs --types token-launch,status --seconds 30
```

## Notes

- This is a **launch feed** (new mints), not a price/trade tape. It does not
  carry per-token price history, holder counts, or buy/sell flow. Pair it
  with Helius RPC (`~/workspace/skills/helius/`) for on-chain verification
  of any mint (supply, authorities, largest accounts).
- Throughput is high (several launches/sec at peak). Always use `--match`,
  `--min-mcap`, or `--limit` rather than dumping the raw firehose.
- Do not use this feed as a trading signal. It is observation only.
