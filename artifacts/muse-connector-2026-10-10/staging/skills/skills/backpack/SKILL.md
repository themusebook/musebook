---
name: backpack
description: Read-only Backpack Exchange market-data client plus the ED25519 request-signing reference for future authenticated use. Authenticated trading is NOT enabled.
---

# Backpack Exchange

Market data from **Backpack Exchange** (never call it a DEX in copy).

- REST base: `https://api.backpack.exchange/`
- WebSocket: `wss://ws.backpack.exchange/`

## Finance boundary

Market data here is research/organization only — never buy/sell advice, never price targets as advice.

## Public market data (verified live 2026-09-18, no auth)

| Endpoint | Notes |
|---|---|
| `GET /api/v1/markets` | All markets; filter by `quoteAsset` client-side |
| `GET /api/v1/ticker?symbol=SOL_USDC` | 24h ticker for one symbol |
| `GET /api/v1/tickers` | All tickers |
| `GET /api/v1/depth?symbol=SOL_USDC` | Order book (`limit` optional) |
| `GET /api/v1/trades?symbol=SOL_USDC&limit=25` | Recent trades |
| `GET /api/v1/klines?symbol=SOL_USDC&interval=1h&startTime=<SEC>&endTime=<SEC>` | Candles. **startTime/endTime are SECONDS, not ms.** Intervals: `1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M` |
| `GET /api/v1/status` | Exchange status |

CLI: `bin/backpack.py` (urllib-based, proxy-safe). Examples:

```bash
bin/backpack.py status
bin/backpack.py markets --quote USDC
bin/backpack.py ticker --symbol SOL_USDC
bin/backpack.py depth --symbol SOL_USDC --limit 20
bin/backpack.py trades --symbol SOL_USDC --limit 25
bin/backpack.py klines --symbol SOL_USDC --interval 1h --hours 24
```

## Authenticated requests (reference only — NOT enabled)

> **Authenticated trading is NOT enabled.** Enabling it requires the user to
> (a) create an exchange API key themselves in their Backpack account,
> (b) store it via the Secure Vault (`credentials.request_api_access`) — never paste a raw seed/key into chat,
> (c) approve in chat the custody scope, allowed market types, per-order and daily caps, leverage, and a withdrawal prohibition.
>
> Never generate or store an ED25519 seed for Backpack. Never ask the user for a raw seed in chat.

When authenticated access is approved later, mutating requests (and some
private reads) use these headers:

| Header | Value |
|---|---|
| `X-Timestamp` | Unix time in **milliseconds** |
| `X-Window` | Validity window in ms; default `5000`, max `60000` |
| `X-API-Key` | Base64-encoded ED25519 verifying key |
| `X-Signature` | Base64-encoded ED25519 signature |

Canonical signing string:

```text
instruction=<instruction>&<alphabetically-sorted params>&timestamp=<ms>&window=<ms>
```

Example:

```text
instruction=orderCancel&orderId=28&symbol=BTC_USDT&timestamp=1614550000000&window=5000
```

Rules:

- Only include parameters actually sent in the signing string.
- For endpoints accepting `orderId` **or** `clientId`, send exactly one — sending both fails signature verification.
- Batch orders: one `instruction=orderExecute` prefix per alphabetically-ordered order payload, concatenated, then `&timestamp=<ms>&window=<ms>`.
- Private WebSocket subscribe signs `instruction=subscribe&timestamp=<ms>&window=<ms>` and sends it as
  `{"method":"SUBSCRIBE","params":[...],"signature":["<verifying key>","<signature>","<timestamp>","<window>"]}`.

Reference implementation: `bin/backpack_sign.py` builds canonical signing
strings and runs a self-test (throwaway test key only, never persisted).
It performs **no authenticated network calls**.
