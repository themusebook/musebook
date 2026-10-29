---
name: "flash"
description: "Use Definitive Flash API when the user asks for Flash, Definitive trading, or this provider's API."
---

# Definitive Flash API

Advanced trading API for AI agents and builders. Solana same-chain order types: market, limit, TWAP, stop, take-profit (stop-loss / take-profit). Bracket orders are documented as same-chain EVM-only — never present bracket as a Solana order type. Non-custodial: funds stay in the user's wallet until execution.

Official Flash MCP reference (read-only / reference use only): npm `@definitive-fi/flash-mcp`, GitHub `DefinitiveCo/flash-mcp`, MIT license. Tools: `flash_setup`, `flash_status`, `flash_quote`, `flash_balances`, `flash_submit_order`, `flash_get_order`, `flash_list_orders`, `flash_cancel_order`. Custody warning: the MCP's normal execution model stores a local Solana private key — that conflicts with the standing browser-signing rule. Use it only as an API reference and/or for read-only non-custodial tools. Never request, import, or store a Flash private key.

Docs: https://flash.definitive.fi/docs/llms.txt

## Auth
API key via `x-definitive-api-key` header. Base URL: `https://flash.definitive.fi/v1`.

The key is stored via `credentials.request_api_access` (service `custom.flash`) — the user pastes it on the secure hosted page, never in chat. The CLI below reads it from the Secure Vault through the credential surrogate helper; it never prints or logs the raw key.

If a request carrying the credential gets 401/403, re-check the request shape first (wrong chain/asset fields look like auth failures). Only then call `credentials.request_api_access` with `reconnect` to replace the key.

## Operating rules
1. Solana only unless the user explicitly names an EVM chain (standing rule: Solana always).
2. Trading = money movement: every quote→order flow needs the user's fresh approval of exact terms (pair, side, qty, order type, limit price, fee bps) before submitting. Quotes are read-only and need no approval.
3. Never ask for the raw key in chat. Never put it in files, env vars, logs, or URLs.
4. Integrator fee: pass `flashIntegratorFeeBps` (string bps, e.g. `"50"`) identically on quote AND order to monetize Musebook flow. Definitive takes 10 bps base (promo through Dec 2026) on top.
5. User signing happens in the user's browser/wallet. The agent prepares quote + setup instructions; the user signs the delegation tx and the offchain order message.

## Solana order flow (quote → delegate → sign → submit)
1. `POST /quote` with targetAsset/contraAsset (base58 mints), targetChain/contraChain (`solana`), side (`buy`/`sell`), qty (decimal string in spent-asset units: contraAsset on buy, targetAsset on sell), orderType, funderAddress.
2. Handle `svm.ataSetupIxs` (create missing ATAs) and `svm.delegateIx` (SPL Approve to Flash program) — one-time per token; can be combined in one tx (ATAs first, then delegation).
3. User Ed25519-signs `svm.orderMessage` → base58 `userSignature`.
4. `POST /order` with trade params + funderAddress, quoteId, userSignature, svmNonce, svmDeadline.
5. Track via `GET /orders/{orderId}`; cancel via `POST /orders/{orderId}/cancel` (signed cancel message).

wSOL mint: `So11111111111111111111111111111111111111112`. Native SOL: set `svmUseNativeSOL: true` and spend the wSOL mint.

## CLIs
- `bin/flash.py` — quote, order, status, cancel, list-orders, balances. Examples:
  `flash.py quote --chain solana --target-asset <mint> --contra-asset <mint> --side sell --qty 1.5 --order-type limit --limit-price 100 --funder <wallet>`
  `flash.py order-status --order-id <id>`
