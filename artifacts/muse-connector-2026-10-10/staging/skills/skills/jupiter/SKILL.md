---
name: "jupiter"
description: "Use Jupiter when the user asks for Jupiter or this provider's API."
---

# Jupiter

## Purpose
Use Jupiter with the user-connected `custom.jupiter` credential.

## Tooling
Add service-specific CLIs under `~/workspace/skills/jupiter/bin/`.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and call `add_surrogate_to_request(...)`, `url_with_surrogate_query_param(...)`, or `url_with_surrogate_path_segment(...)` before authenticated requests, matching where the provider reads the key. If they use `urllib`, read JSON responses with `read_json_response(resp)` from the same helper instead of calling `resp.read()` directly. They must send only `hsurr:*` values, and only to the hosts below.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.jupiter`.

## Predictions (Jupiter Forecast / Prediction API)
Base: `https://api.jup.ag/prediction/v1` — **BETA, breaking changes possible.**
CLI: `bin/jup_predict.py` — same stored `custom.jupiter` credential, restricted to `api.jup.ag`.
Auth format: the key goes in the **`x-api-key`** header on `api.jup.ag`
(not Bearer — mcp.jup.ag uses Bearer, see Trading MCP below).
Verified against the official OpenAPI spec + guides on 2026-09-18.

### Providers
`bisonfi` (Jupiter Forecast), `polymarket`, `kalshi`, `gx`. Events endpoints
take `?provider=` (bisonfi for Forecast). CLI `events` defaults to bisonfi;
`events-search`/`suggested` default to polymarket per the API default.

### Read-only endpoints (CLI command -> API)
- `trading-status` -> `GET /trading-status`
- `vault-info` -> `GET /vault-info` (settlement mint, contract caps, fee bps)
- `forecast --market-id` -> `GET /forecast?marketId=` (price time-series)
- `events` -> `GET /events` (filters: category, subcategory, tags, new/live/
  trending/upcoming, sortBy volume|beginAt; pagination via start/end)
- `events-search --query` -> `GET /events/search` (limit 1-20)
- `event <id>` -> `GET /events/{eventId}`
- `suggested <owner>` -> `GET /events/suggested/{pubkey}`
- `scores --event-ids A,B` / `event-score <id>` -> `GET /events/scores`, `/events/{id}/score`
- `event-markets <id>`, `event-market <id> <market>` -> `GET /events/{id}/markets[/{marketId}]`
- `market <id>` -> `GET /markets/{marketId}` (flat fields; event title in event.metadata)
- `orderbook <id>` -> `GET /orderbook/{marketId}` (prints exact `yes_dollars`/
  `no_dollars` levels; rounded cent arrays can show 0 for sub-cent prices)
- `positions <owner>` -> `GET /positions` (filters: market-id, market-pubkey,
  is-yes; --bisonfi is client-side Forecast filtering)
- `position <pubkey>` -> `GET /positions/{positionPubkey}`
- `orders <owner>` -> `GET /orders`; `order <pubkey>` -> `GET /orders/{orderPubkey}`;
  `order-status <pubkey>` -> `GET /orders/status/{orderPubkey}` (status + history)
- `history <owner>` -> `GET /history` (filters: position-pubkey, id)
- `profile <owner>` -> `GET /profiles/{ownerPubkey}`; `pnl-history` -> interval 24h|1w|1m
- `trades` -> `GET /trades` (recent fills, global)
- `leaderboards` -> `GET /leaderboards` (period all_time|weekly|monthly, metric
  pnl|volume|win_rate, limit 1-100)

### Value-bearing builds (unsigned tx only — browser signs, then execute)
Flow: `buy`/`sell`/`sell-all`/`claim` build -> user signs in browser ->
`execute --signed-tx <base64> --context '<ctx json>'` posts to `/execute`.
`execution.context` (type `create_order` keeper-filled, or `bisonfi_swap`
Forecast) must be passed UNCHANGED. `sell` closes the ENTIRE position.
`claim` is for claimable winners (unclaimed wins auto-claim ~24h after
settlement; Forecast has no claim step — it auto-settles).
After placing a non-Forecast order, monitor it with
`order-status <orderPubkey>` (`GET /orders/status/{orderPubkey}` — status +
history) until the keeper reports `filled`/`failed` (interim statuses can
show `created`/`partiallyfilled`).

### Limits (official)
- Forecast (bisonfi): **USDC only, 5-250 USDC** per order. Closed round -> 
  `bisonfi_market_not_tradable`; no routable liquidity -> `no_route`; Forecast
  sells need >= 0.01 outcome tokens (`bisonfi_position_too_small`).
- General: JupUSD or USDC, minimum 5 USD. Deposits: USDC
  `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`, JupUSD
  `JuprjznTrTSp2UFa3ZBUFgwdAmtZCq4MQCwysN55USD`.
- Units: 1_000_000 micro units = $1; 1_000_000 micro-contracts = 1 contract.
  Always prefer `contractsMicro`/`contractsDecimal` over legacy `contracts`.

### Forecast facts (verified live 2026-09-18)
- Markets are 15m BTC up/down rounds; live IDs are `BISON-<eventPda>-UP/DOWN`
  (resolve via `events --provider bisonfi --filter live --include-markets`;
  do NOT hardcode market IDs).
- No CLOB for bisonfi: `/orderbook` returns 502 `orderbook_bad_status` and
  events pricing is null — price is set at order-build time via the atomic swap.
- Each outcome is a Token-2022 mint (`outcomeMint`); larger-than-250-USDC
  sizes can trade outcome tokens directly via the Swap API path.
- Order statuses: pending/filled/failed (keep status may also show
  created/partiallyfilled). Forecast positions appear after `/execute`;
  no order-status polling needed for bisonfi.

## Operating Rules
1. Use this skill when the user asks for Jupiter or this provider's API.
2. Restrict authenticated requests to: api.jup.ag.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.

## Trading MCP (hosted, keyless-verified 2026-09-18)
- Server: `https://mcp.jup.ag` — Streamable HTTP, POST JSON-RPC to the root path
  `/` (not `/mcp`). `GET /health` returns `{"status":"ok"}` unauthenticated.
- Keyless works at a lower rate limit; the same Jupiter API key raises the limit
  as `Authorization: Bearer <key>`. That is a different header format than
  api.jup.ag's `x-api-key`, so keyed MCP access uses a separate scoped
  credential `custom.jupiter-mcp` (hosts: mcp.jup.ag, placement: bearer_header)
  — connected 2026-09-18 and verified live (Bearer attach + tools/list = 75).
  Do not attach the `custom.jupiter` x-api-key credential to mcp.jup.ag.
- Verified live: `initialize` + `tools/list` returns 75 tools across 11 domains
  (tokens 7, price 1, trigger 10, recurring 4, lend 11, prediction 27,
  portfolio 3, swap 3, transaction 1, send 4, studio 4).
- Read-only docs MCP (documentation only, no execution):
  `https://developers.jup.ag/docs/mcp`.
