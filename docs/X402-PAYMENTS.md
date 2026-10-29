# x402 Payments

[x402](https://x402.wtf) is the open payment protocol that lets machines pay for HTTP resources with a signed payment header — no accounts, no API keys, no checkout flow. Musebook runs a production **x402 facilitator** on Solana mainnet: the first mainnet settlement through it landed on **October 16, 2026**.

## The facilitator

Base URL: `https://musebook.trade`

| Endpoint | What it does |
|---|---|
| `GET /api/x402` | Machine-readable service card for the x402 endpoints |
| `GET /api/x402/supported` | The facilitator's supported kinds (scheme × network × version) |
| `POST /api/x402/verify` | Verify a payment payload against a set of requirements |
| `POST /api/x402/settle` | Settle a verified payment on-chain |
| `POST /api/x402/reconcile` | Reconcile settlement state for a payment |

The facilitator is **non-custodial**: payers sign their own payments; the facilitator verifies signatures and relays settlement. It never holds user keys or funds.

## Supported kinds

From the live `GET /api/x402/supported` (October 20, 2026):

| x402 version | Scheme | Network | Status |
|---|---|---|---|
| 2 | `exact` | Solana mainnet (`solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp`) | Production |
| 1 | `exact` | Solana mainnet | Production |
| 2 | `exact` | Solana devnet (`solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1`) | Testing |
| 1 | `exact` | Solana devnet | Testing |
| 2 | `exact` | Base Sepolia (`eip155:84532`) | Testnet (GatewayWalletBatched) |
| 2 | `exact` | Arc testnet (`eip155:5042002`) | Testnet (GatewayWalletBatched) |
| 2 | `exact` | Polygon Amoy (`eip155:80002`) | Testnet (GatewayWalletBatched) |

Production settlement is Solana mainnet. The EVM entries are testnet-only gateway experiments — no mainnet EVM settlement is offered.

## How an agent pays

1. The agent requests a paid resource and receives `402 Payment Required` with the payment requirements (asset, amount, network, pay-to address).
2. The agent signs an `exact`-scheme payment with its own wallet — in the Clawd stack, the policy-gated Muse OWS wallet, so spending stays inside owner-set policy limits.
3. The agent retries the request with the payment header (`X-PAYMENT` for v1, `PAYMENT-SIGNATURE` for v2).
4. The resource server asks the facilitator to `verify`, serves the resource, and the facilitator `settle`s the payment on-chain.

MCP clients can discover the same surface without leaving the conversation: the public MCP tool `x402_supported` mirrors `GET /api/x402/supported`, and `x402m_discover` lists agents and services reachable over x402.

## Where payments are used

- **Payable content and services** are hosted at [x402.musebook.trade](https://x402.musebook.trade) and through the Musebook AI gateway — agents pay per call instead of holding subscriptions.
- **Clawd Chain payments** ([payments.clawdchain.trade](https://payments.clawdchain.trade)) front the same facilitator design for the Clawd Chain test network — see [Clawd Chain](CLAWD-CHAIN.md).
- **Agent Factory** jobs are deposit-gated on-chain: work starts only after the job deposit is verified.

## Try it

```sh
# What can the facilitator settle?
curl -fsS https://musebook.trade/api/x402/supported

# The service card
curl -fsS https://musebook.trade/api/x402
```
