# Clawd Live Relay — clawd-ws.fly.dev

The Clawd live relay is a **public, no-auth WebSocket stream** of real-time
Solana activity, operated by the Clawd agent ecosystem. Its flagship feed is
the pump.fun new-token launch stream: one frame per new pump.fun mint, usually
seconds after the mint transaction confirms.

Dashboard: `https://clawd-ws.fly.dev/`
Stream: `wss://clawd-ws.fly.dev/ws`

No account, API key, or login is needed. The relay is observation-only
infrastructure — it never signs, never broadcasts transactions, and never
requires a wallet.

## Why this matters to the Clawd × Privy agent

- **Token verification workflows:** when a user asks "is this new token legit?",
  the agent can describe how to watch the relay for the launch frame, pull the
  mint/creator/signature, then verify on-chain (supply, authorities, holders)
  before recommending any wallet action.
- **Agent discovery:** new agents and tokens surface on the relay before they
  appear in curated directories — useful context for auto.exchange agent
  questions ("which agents exist for X?").
- **Privy + launches:** patterns like "watch for launches matching a name, then
  build a Privy server-wallet buy flow for the verified mint" start with this
  stream. The relay is the *detection* half; Privy wallets are the *execution*
  half.

## Connecting

### The handshake rules

The server **requires an `Origin` header** on the WebSocket handshake
(browser-like). Node's built-in WebSocket (undici) does not send one by
default and will fail — use the `ws` npm package with an explicit header:

```js
import WebSocket from "ws";

const ws = new WebSocket("wss://clawd-ws.fly.dev/ws", {
  headers: {
    Origin: "https://clawd-ws.fly.dev",
    "User-Agent": "my-app/1.0",
  },
  handshakeTimeout: 15000,
});
```

Behind a corporate/restricted egress proxy, route the socket through it —
`ws` does not read proxy env vars on its own:

```js
import { HttpsProxyAgent } from "https-proxy-agent";

const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY || null;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;

const ws = new WebSocket("wss://clawd-ws.fly.dev/ws", {
  agent,
  headers: { Origin: "https://clawd-ws.fly.dev" },
});
```

Python equivalent (pattern — verify against your installed client version):

```python
import websocket  # websocket-client

ws = websocket.WebSocketApp(
    "wss://clawd-ws.fly.dev/ws",
    header={"Origin: https://clawd-ws.fly.dev"},
    on_message=on_message,
)
ws.run_forever()
```

### Reconnection

The relay may drop idle or long-lived sockets. A robust consumer:

1. Reconnects with bounded exponential backoff (1s → 30s max).
2. Tracks the last received frame time and treats silence as a signal to
   re-dial, not as "no launches happening".
3. Deduplicates on `signature` (each launch frame carries the mint
   transaction signature).

```js
let backoff = 1000;
function connect() {
  const ws = new WebSocket(URL, { headers: { Origin: "https://clawd-ws.fly.dev" } });
  ws.on("open", () => { backoff = 1000; });
  ws.on("message", handle);
  ws.on("close", () => {
    setTimeout(connect, backoff + Math.random() * 500);
    backoff = Math.min(30000, backoff * 2);
  });
  ws.on("error", (e) => console.error("relay error:", e.message));
}
```

## Frame types

Every frame is JSON text. Unknown `type` values may appear — pass them
through rather than crashing.

### `status` — heartbeat

```json
{
  "type": "status",
  "connected": true,
  "uptime": 1234567,
  "totalLaunches": 891234,
  "githubLaunches": 1203,
  "totalClaims": 0,
  "clients": 42
}
```

| Field | Meaning |
|---|---|
| `connected` | Relay health flag |
| `uptime` | Server uptime (unit varies; treat as informational) |
| `totalLaunches` | Cumulative launch frames emitted |
| `githubLaunches` | Launches whose metadata links a GitHub repo |
| `totalClaims` | Cumulative claim-type events (informational) |
| `clients` | Currently connected subscribers |

### `token-launch` — one per new pump.fun mint

```json
{
  "type": "token-launch",
  "time": "2026-09-22T16:20:00.000Z",
  "name": "Example Token",
  "symbol": "EXMPL",
  "mint": "8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump",
  "creator": "CreatorWalletAddress...",
  "signature": "mintTransactionSignature...",
  "metadataUri": "https://...",
  "imageUri": "https://...",
  "description": "Token description (may be empty)",
  "marketCapSol": 12.5,
  "website": "https://...",
  "twitter": "https://x.com/...",
  "telegram": "https://t.me/...",
  "isV2": false,
  "hasGithub": false,
  "githubUrls": []
}
```

| Field | Meaning |
|---|---|
| `time` | When the relay emitted the frame (ISO-8601) |
| `name` / `symbol` | Token name and ticker (unverified, creator-supplied) |
| `mint` | Token mint address — the on-chain identifier |
| `creator` | Wallet that created the token |
| `signature` | The mint/creation transaction signature |
| `metadataUri` / `imageUri` | Off-chain metadata and logo |
| `description` | Creator-supplied description (treat as untrusted) |
| `marketCapSol` | Market cap in SOL **at launch detection time** |
| `website` / `twitter` / `telegram` | Social links (often absent) |
| `isV2` | Whether the token launched on pump.fun v2 rails |
| `hasGithub` / `githubUrls` | Whether metadata references a GitHub repo |

## Filtering patterns

Throughput is high — several launches per second at peak. Never dump the raw
firehose; filter client-side:

```js
ws.on("message", (buf) => {
  const d = JSON.parse(buf.toString("utf8"));
  if (d.type !== "token-launch") return;

  // 1. Minimum market cap
  if ((d.marketCapSol || 0) < 50) return;

  // 2. Must have a twitter link
  if (!d.twitter) return;

  // 3. Name/symbol/description match
  const hay = `${d.name} ${d.symbol} ${d.description}`;
  if (!/clawd/i.test(hay)) return;

  console.log(JSON.stringify({
    time: d.time, name: d.name, symbol: d.symbol, mint: d.mint,
    creator: d.creator, marketCapSol: d.marketCapSol,
    twitter: d.twitter, telegram: d.telegram, website: d.website,
    signature: d.signature,
  }));
});
```

Common filter combinations:

- `--match REGEX` — name/symbol/description substring or regex match
- `--min-mcap SOL` — floor on launch-time market cap
- `--has-twitter` — only launches with a linked X account
- `--limit N` — stop after N matching events
- `--seconds N` — time-boxed watch sessions

## What the feed is NOT

- **Not a price tape.** Frames carry launch-time market cap only. There is no
  per-token price history, candle data, holder counts, or buy/sell flow.
- **Not verified data.** Names, symbols, descriptions, and social links are
  creator-supplied and frequently impersonate legitimate projects. Every
  security-relevant claim must be re-verified on-chain.
- **Not a trading signal.** It is observation infrastructure. Any trading
  decision needs independent verification (see below).

## Verifying a launch on-chain

When a user asks about a token seen on the relay, the agent should describe
(and, when it has RPC access, perform) these checks before any wallet
involvement:

1. **Mint exists and matches** — fetch the mint account; confirm supply and
   decimals.
2. **Authorities** — check mint authority and freeze authority. Renounced
   (null) authorities are the common "safer" pattern; live authorities are a
   red flag to disclose.
3. **Creator vs mint relationship** — the `creator` field is the deployer;
   large creator holdings post-launch are worth flagging.
4. **Metadata** — resolve `metadataUri`; confirm name/symbol match the frame.
5. **Liquidity / market** — launch frames do not carry pool state; check the
   bonding curve or AMM pool separately.

Recommended RPC: Helius (fast, no rate-limit stalls on the free tier for
light reads). Public endpoints work for one-off checks.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Handshake fails / 403 | Missing `Origin` header | Send `Origin: https://clawd-ws.fly.dev` (the `ws` package, not undici) |
| `ws` package not found | Not installed | `npm install ws` (and `https-proxy-agent` if proxied) |
| Connects but no frames for minutes | Normal at quiet hours, or a stale socket | Track last-frame time; reconnect if silent > 60s |
| Duplicate launches after reconnect | Replayed buffer on re-dial | Deduplicate on `signature` |
| Frames with unknown `type` | Relay added a new event kind | Pass through / log; do not crash |

## Quick reference

- Stream: `wss://clawd-ws.fly.dev/ws`
- Dashboard: `https://clawd-ws.fly.dev/`
- Auth: none (public)
- Required handshake header: `Origin: https://clawd-ws.fly.dev`
- Primary frames: `status`, `token-launch`
- Dedup key: `signature`
- Launch identity: `mint`
- Trust level: **untrusted until verified on-chain**
