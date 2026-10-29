---
name: "dflow"
description: "Use Dflow when the user asks for Dflow or this provider's API."
---

# Dflow

## Purpose
Use Dflow with the user-connected `custom.dflow` credential. Read-only market data only — no wallet signing, no trading — unless the user separately authorizes it.

## Tooling
CLIs under `~/workspace/skills/dflow/bin/` (all read-only):

- `dflow_quote.py <inputMint> <outputMint> <amount_atomic> [--sign] [--watch SEC]` — spot quote via `GET /order` (no `userPublicKey`, no transaction attached). `--sign` requests an RFC 9421 signed response and verifies it against DFlow's pinned Ed25519 key, failing closed on any mismatch. `--watch SEC` polls one compact line per interval. Verified working 2026-09-18.
- `dflow_markets.py list [--status active] [--limit N] [--cursor C]` — Kalshi prediction markets via `GET /api/v1/markets` on `d.prediction-markets-api.dflow.net`. Prices are decimal fractions of $1 (0.62 = 62c). Note: the server ignores the `search` param. Verified working 2026-09-18.
- `dflow_markets.py show <TICKER>` — full market detail (bid/ask, volume, OI, close date, settlement rails with yesMint/noMint). Scans pages via cursor; no single-ticker endpoint exists. Verified working 2026-09-18.
- `dflow_stream.py <baseMint> <quoteMint> [--seconds N] [--dev]` — live per-slot bid/ask via WebSocket. `--dev` uses the keyless dev stream (`wss://dev-quote-api.dflow.net/quote-stream`, rate-limited, works). Production (`wss://quote-api.dflow.net/quote-stream`) is **gated per API key**: this key gets HTTP 404 on the stream (403 without key), i.e. stream access is not enabled — use `--dev` or `dflow_quote.py --watch` instead. Node + `ws` + `https-proxy-agent` through the egress proxy; the API key travels only as the proxy-resolved surrogate in argv, never logged. Verified 2026-09-18.
- `dflow_trade.py prepare --in <MINT> --out <MINT> --amount <ATOMIC> [--slippage-bps N] [--priority-fee auto|medium|high|veryHigh|disabled|N] [--user <PUBKEY>]` — builds a live trade via production `GET /order` for the dflow-trader wallet (default) or an override pubkey; saves the UNSIGNED base64 transaction + exact terms to `~/workspace/dflow/trades/`. Enforces per-trade cap (0.05 SOL) and daily cap (1 SOL, UTC) on SOL-input trades. Prints terms for approval. Verified against production 2026-09-18.
- `dflow_trade.py sign --file <PREP_JSON> [--password-stdin]` — signs the prepared transaction with the local dflow-trader wallet (password transient, never stored). Refuses re-sign and pubkey mismatch. Requires the user's explicit per-trade approval in chat before running. Signature cryptographically verified 2026-09-18.
- `dflow_trade.py broadcast --file <PREP_JSON> [--signed-tx <BASE64>]` — submits the signed transaction via Helius mainnet RPC and confirms against the blockhash DFlow signed with. Rejects unsigned/malformed txs client-side, surfaces chain rejections cleanly, records spend to `~/.vulcan/wallets/dflow-trader-state.json`. Verified end-to-end 2026-09-18 (chain rejected the unfunded test wallet with AccountNotFound, as expected).
- `dflow_wallet.py create [--password-stdin]` / `dflow_wallet.py pubkey` — local dflow-trader wallet (user-approved exception 2026-09-18, like clawd-buyer). Secret encrypted at rest with scrypt (N=2^15, r=8, p=1) + XSalsa20-Poly1305, file 0600 at `~/.vulcan/wallets/dflow-trader.json`. Password never stored — supplied transiently per session. `DFLOW_WALLET_PATH` env overrides the path (tests).
- `dflow_client.py` — shared module: `dflow_get(host, path, params, extra_headers)` via the connector surrogate, plus `verify_signed_response(...)` implementing fail-closed RFC 9421 verification (content-digest check, canonical signature-base rebuild, Ed25519 against the pinned key `EZKxYr7bbXHaKAGw2MEpVUU9He3hwXGejSpCsdsZCmiF`, x-request-id replay binding, `created` freshness ±300s). Cross-checked against the `http-message-signatures` reference library.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and call `add_surrogate_to_request(...)`, `url_with_surrogate_query_param(...)`, or `url_with_surrogate_path_segment(...)` before authenticated requests, matching where the provider reads the key. If they use `urllib`, read JSON responses with `read_json_response(resp)` from the same helper instead of calling `resp.read()` directly. They must send only `hsurr:*` values, and only to the hosts below.

**Transport:** use `urllib` with a 60s timeout, not `curl`. The surrogate is only swapped for the real key on the approved urllib path — the same request via `curl` reached DFlow unauthenticated (403). (Large-response truncation that hit the Hyperliquid skill does not apply here; quote responses are small.)

**RFC 9421 gotchas (learned 2026-09-18):** the covered component id keeps its item parameters, so the base line is `"x-request-id";req: <value>`, not `"x-request-id": <value>`. The `@signature-params` line must include the inner-list params (`;created=…;keyid="…";alg="ed25519"`), not just the `(...)` list.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.dflow`.

## Operating Rules
1. Use this skill when the user asks for Dflow or this provider's API.
2. Restrict authenticated requests to: quote-api.dflow.net, d.prediction-markets-api.dflow.net, pond.dflow.net.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.
5. Read-only by default. Wallet use, signing, or trading needs separate explicit user approval.
