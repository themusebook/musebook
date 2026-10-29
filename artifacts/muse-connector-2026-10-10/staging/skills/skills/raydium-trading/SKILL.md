---
name: "raydium-trading"
description: "Trade on Raydium (Solana AMM/CLMM) via the public Trade API. Quote swaps, build unsigned swap transactions for the user's browser wallet to sign, broadcast user-signed transactions. Browser-signing only — the agent never holds a private key."
---

# Raydium Trading

Spot swaps on Raydium's AMM / CLMM / AMM v4 pools through the public,
keyless Trade API (`transaction-v1.raydium.io`) — the same surface the
Raydium UI uses. No API key, no account, no local wallet needed.

## Signing rule (non-negotiable)

- The agent **builds** the transaction; the **user signs** it in their own
  browser wallet. The agent never signs for the user.
- Every swap needs the user's fresh approval of the exact terms: input mint,
  output mint, amount, slippage. Show the quote before asking.
- Quote responses expire quickly (~30s). Build and present promptly; do not
  cache quotes across a long conversation.

## CLI

`bin/raydium.py` — pure stdlib for quote/build/price (solders only needed
for the optional `broadcast` path).

### Quote (read-only, no wallet)

```bash
bin/raydium.py quote \
  --input-mint So11111111111111111111111111111111111111112 \
  --output-mint EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v \
  --amount 100000000 \
  --slippage-bps 50
```

`--amount` is in base units (lamports for SOL, mint decimals otherwise).
Returns expected output, minimum received after slippage, price impact, and
the route plan (pool IDs).

### Build an unsigned swap (user signs in browser)

```bash
bin/raydium.py build \
  --input-mint So11111111111111111111111111111111111111112 \
  --output-mint EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v \
  --amount 100000000 \
  --wallet <USER_WALLET_PUBKEY> \
  --slippage-bps 50 \
  --priority-fee 50000
```

Returns `unsigned_tx` (base64 VersionedTransaction) plus the quote details.
Hand the base64 to the user's wallet to sign. The transaction is only valid
for the wallet passed as `--wallet` (fee payer).

### Broadcast a user-signed transaction

```bash
bin/raydium.py broadcast --signed-tx <BASE64_FROM_WALLET> [--rpc URL]
```

Prefer letting the user's wallet broadcast (wallet-adapter `sendTransaction`
does sign + broadcast in one step). Use `broadcast` only when the wallet
returns a signature-less signed transaction.

### USD prices

```bash
bin/raydium.py price --mints <MINT> [<MINT>...]
```

## Recommended agent flow

1. `quote` → show the user: "Swap X SOL → ~Y USDC on Raydium (min Z after
   0.5% slippage, price impact P%). Approve?"
2. On approval: `build --wallet <their pubkey>` → present the unsigned tx
   for browser signing.
3. Confirm the signature on-chain (Solscan link) before reporting success.

## Notes

- Raydium routes CPMM, CLMM, and AMM v4 pools; the Trade API picks the route.
  For Jupiter's aggregator (which includes Raydium among others), see the
  `jupiter` skill. For DFlow's order flow, see `dflow-spot-trading`.
- Priority fee default is 50,000 micro-lamports/CU; raise under congestion.
- Verified live 2026-10-02: `compute/swap-base-in` quote for 0.1 SOL → USDC
  returned a valid route plan.
