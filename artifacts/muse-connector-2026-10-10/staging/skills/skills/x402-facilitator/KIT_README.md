# muse-facilitator-kit

Run your own **x402 facilitator** (Solana + EVM) with the **x402m m2m meta
protocol**: single-signature batch settlement, public receipts, and the
machine-economy pulse. Built for Muse agents, by the x402m reference
implementation.

**Live reference facilitator:** https://musebook.trade
(`/.well-known/x402-facilitator`)

## What it is

An x402 facilitator is the machine-economy cashier: it **verifies** that a
payer signed a valid payment, then **settles** it on-chain. x402m extends x402
with:

- **Batch settlement** — one payer, one signature, up to 8 USDC payments in a
  single Solana transaction (`x402m-batch-v0`)
- **EVM relay** — verify EIP-712/EIP-3009 authorizations, relay via
  `transferWithAuthorization` (`x402m-evm-relay-v0`)
- **Facilitator discovery** — `/.well-known/x402-facilitator` descriptor
- **Receipts + pulse** — a public m2m payment tape and 24h economy stats

The kit is **non-custodial**: the facilitator verifies and relays. The payer
signs. The facilitator never holds user funds and never signs as authority.

## Quickstart

```bash
npx muse-facilitator-kit init --chain solana --network mainnet
# or: --chain evm|both   --network devnet

cp .env.example .env   # fill in RPC URLs / relay key as needed
npx muse-facilitator-kit serve --port 8787
```

Then:

```bash
curl localhost:8787/.well-known/x402-facilitator | jq .
curl localhost:8787/api/x402/batch/ping
```

## How a Muse agent uses a facilitator

1. **Discover** — `GET /.well-known/x402-facilitator` on any facilitator
   domain. No human in the loop.
2. **Plan** — `POST /api/x402/batch/plan` with `{network, payer, payments[]}`.
   You get back an **unsigned** transaction template + quote.
3. **Sign** — the payer signs the transaction in their own wallet (browser,
   OWS policy-gated key, etc.). The facilitator never sees a private key.
4. **Verify** — `POST /api/x402/batch/verify` with the signed bytes. The
   facilitator checks every instruction is a `TransferChecked` for the exact
   asset, amounts, recipients, and signatures.
5. **Settle** — `POST /api/x402/batch/settle`. One transaction is broadcast;
   one receipt is written to the public tape.

For EVM: sign an EIP-712 `TransferWithAuthorization` client-side and send it
to `POST /api/x402/batch/settle-multi`. See `CLIENT_EXAMPLE.md`.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/.well-known/x402-facilitator` | discovery descriptor |
| GET | `/api/x402/supported` | x402 kinds (incl. x402m extensions) |
| GET | `/api/x402/batch/ping` | health |
| POST | `/api/x402/batch/plan` | Solana: unsigned batch tx template |
| POST | `/api/x402/batch/verify` | Solana: strict structural verify |
| POST | `/api/x402/batch/settle` | Solana: broadcast one batch tx |
| POST | `/api/x402/batch/settle-multi` | N envelopes, Solana and/or EVM |
| POST | `/api/x402/verify` | single x402 exact (Solana) |
| POST | `/api/x402/settle` | single x402 exact (Solana) |
| GET | `/api/x402/receipts` | public m2m payment tape |
| GET | `/api/x402/pulse` | 24h settlements, volume, top pairs/referrers |
| GET | `/api/x402/facilitators` | registry (this facilitator) |

## Configuration

`facilitator.config.json`:

```json
{
  "id": "my-facilitator",
  "operator": "muse-agent",
  "networks": ["solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"],
  "port": 8787,
  "baseUrl": "https://facilitator.example.com"
}
```

`.env` (never commit):

- `SOLANA_RPC_URL`, `SOLANA_DEVNET_RPC_URL`, `BASE_RPC_URL`,
  `BASE_SEPOLIA_RPC_URL` — custom RPCs (optional; public defaults otherwise)
- `FACILITATOR_EVM_KEY` — **optional** 64-hex key enabling EVM settlement.
  Without it, EVM verify works but settle returns `503
  evm_relay_not_configured`. The key only ever submits other parties' signed
  authorizations and pays gas. Use a dedicated, low-balance hot wallet.
- `FACILITATOR_BASE_URL` — public URL advertised in the descriptor.

## Security notes

- **Never commit `.env` or any private key.** The `.env.example` is a
  template only.
- The EVM relay key cannot move its own funds by design — it only calls
  `transferWithAuthorization` on the declared USDC contract with third-party
  signatures. Still: dedicated hot wallet, minimal balance, rotate freely.
- Batch verify enforces a strict instruction allowlist (only `TransferChecked`
  for the exact USDC mint, payer as sole authority). Anything else is
  rejected before broadcast.
- Built-in per-IP rate limits are best-effort in-memory; put the kit behind a
  real reverse proxy / WAF for production.
- Receipts and pulse are in-memory (cap 500). For production, persist to a DB
  or KV store.
- **Experimental v0.** The Solana batch path is the safe default (payer-signed
  transactions, no facilitator keys). The EVM relay path is new and unaudited —
  run it on testnet first and consider the audited `@x402/evm` facilitator
  for canonical production EVM settlement.

## The user's claim

The user behind x402m asserts this is the world's first m2m x402 meta
protocol and the first x402 facilitator with single-signature batch
settlement. That is the user's public claim, not an independently verified
fact. The protocol is designed to be verifiable: run the kit, read the
receipts, check the claims on-chain.
