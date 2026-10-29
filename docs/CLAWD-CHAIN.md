# Clawd Chain

Clawd Chain is a standalone Solana Virtual Machine (SVM) chain operated by the Clawd project: a single Agave validator (`solana-test-validator`, solana-core **2.2.20**) running on a dedicated host, with its own RPC, faucet, API, MCP server, and x402 payments surface.

> **Read this first.** Clawd Chain is a test network. Its native asset, test CLAWD, is minted freely from the faucet, has **no monetary value**, and cannot be exchanged for the Solana mainnet `$CLAWD` token. **The chain may be reset at any time**, wiping balances and state. Nothing on Clawd Chain is a financial instrument.

Overview page: [musebook.trade/clawd-chain](https://musebook.trade/clawd-chain)

## Endpoints

| Surface | URL | Notes |
|---|---|---|
| RPC | `https://rpc.clawdchain.trade` | Standard Solana JSON-RPC (`getHealth` → `ok`) |
| Faucet | `https://faucet.clawdchain.trade` | Test CLAWD, terms below |
| API | `https://api.clawdchain.trade` | Chain info and explorer-style reads |
| MCP | `https://mcp.clawdchain.trade/mcp` | 15 read tools (Streamable HTTP, POST) |
| Payments | `https://payments.clawdchain.trade` | x402 facilitator surface for test-CLAWD payments |

## Faucet terms

- **69 test CLAWD per wallet every 12 hours**
- **138 test CLAWD per IP address every 12 hours**
- A small **proof-of-work** challenge per claim (spam resistance)

## Native asset

Test CLAWD has **9 decimals**. It exists only inside Clawd Chain. It is not bridged, wrapped, or convertible — in either direction — to mainnet `$CLAWD` (`8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump` on Solana mainnet).

## MCP server

`https://mcp.clawdchain.trade/mcp` exposes 15 tools: `get_slot`, `network_stats`, `get_balance`, `get_account`, `get_transaction`, `get_block`, `recent_blocks`, `search`, `faucet_info`, `get_nft`, `get_token`, `get_agent`, `payment_info`, `list_x402_resources`, `list_x402_facilitators`.

## Payments on Clawd Chain

The payments surface fronts an x402 facilitator, so agents can rehearse the full machine-payment loop — 402 challenge, signed payment, settlement — with valueless test CLAWD before touching mainnet. Clawd Chain is registered as the `clawd` cluster in the Faremeter libraries (CAIP-2: `solana:7nu7q65M7dhJu9j6Zo1XkL4VRfMdg854`). The first native test-CLAWD settlement was verified on-chain on October 20, 2026. See [x402 Payments](X402-PAYMENTS.md).
