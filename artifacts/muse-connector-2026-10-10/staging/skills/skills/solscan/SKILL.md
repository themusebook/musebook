# Solscan Pro API skill

Query Solana on-chain data through the Solscan Pro API (v2.0). The same
indexed data layer that powers solscan.io: decoded transactions, account
history, token metadata/prices/holders, NFT activity, blocks, and DEX/market
data. Mainnet only — no testnet support.

- Base URL: `https://pro-api.solscan.io/v2.0`
- Auth: API key in the `token` request header (not Bearer, not a query param).
  Provided by the `custom.solscan` connector via authd surrogate exchange —
  the key is never read, printed, or persisted by this skill.
- Every call costs 100 CU. Lite plan excludes `account/metadata`,
  `account/funded_by`, and bulk "multi" endpoints.
- Error envelope: `{"success": false, "errors": {"code": <n>, "message": "<s>"}}`.
  A 401 "Unauthorized: Please upgrade your api key level." means the key is
  not activated or the plan doesn't cover that endpoint — check Profile → API
  Management → "Activate my API key" at solscan.io.

## CLI

`bin/sscan.py <METHOD> <PATH> [--data JSON]` — generic authenticated
passthrough. Prints the provider JSON verbatim.

```bash
python3 bin/sscan.py GET "/account/detail?address=<wallet>"
python3 bin/sscan.py GET "/account/transactions?account=<wallet>&limit=10"
python3 bin/sscan.py GET "/token/meta?address=<mint>"
python3 bin/sscan.py GET "/token/price?address=<mint>"
python3 bin/sscan.py GET "/transaction/detail?tx=<signature>"
python3 bin/sscan.py GET "/block/last"
```

## Endpoint paths (verified live 2026-09-22)

These paths were verified by calling the live API with the connected
credential. A 401-level response ("upgrade your api key level") confirms the
route exists but the key's plan/activation doesn't cover it; an empty-body
404 means the path itself is wrong.

| Path | Notes |
| --- | --- |
| `/block/last` | latest block (route exists) |
| `/token/meta?address=<mint>` | token metadata (route exists) |
| `/account/detail?address=<addr>` | account detail (route exists) |
| `/account/transactions?account=<addr>&limit=10` | docs' own curl example; route exists |
| `/chaininfo` | 404 — not a v2.0 path |
| `/chain/info` | 404 — not a v2.0 path |

Docs: https://pro-api.solscan.io/pro-api-docs
MCP alternative: Solscan also hosts an MCP server at https://mcp.solscan.io/mcp
(SOLSCAN_API_KEY env var) with semantic tools over the same data.
