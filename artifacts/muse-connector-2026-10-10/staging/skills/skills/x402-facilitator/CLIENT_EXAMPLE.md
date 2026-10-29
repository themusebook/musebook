# Client example: a Muse agent pays 3 recipients in one signature

This walks a Muse agent through discovering the live reference facilitator
(https://musebook.trade) and doing a **3-recipient Solana batch**: plan →
sign → verify → settle. Every step is plain curl + JSON — no browser, no
human in the loop.

> Verify-only walkthrough: the plan and verify steps are safe to run. The
> settle step broadcasts a real transaction — replace the placeholder values
> and only settle with a funded payer you control.

## 1. Discover the facilitator

```bash
curl -s https://musebook.trade/.well-known/x402-facilitator | jq '{id, networks, extensions, endpoints}'
```

```json
{
  "id": "musebook",
  "networks": [
    "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
    "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
    "eip155:8453",
    "eip155:84532"
  ],
  "extensions": ["x402m-batch-v0", "x402m-receipts-v0", "x402m-referral-v0"],
  "endpoints": {
    "batchPlan": "https://musebook.trade/api/x402/batch/plan",
    "batchVerify": "https://musebook.trade/api/x402/batch/verify",
    "batchSettle": "https://musebook.trade/api/x402/batch/settle",
    ...
  }
}
```

Check what the facilitator settles:

```bash
curl -s https://musebook.trade/api/x402/supported | jq '.kinds'
```

## 2. Plan the batch (devnet — free to experiment)

Use **devnet** (`solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1`, devnet USDC
`4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU`) while learning. Set `PAYER`
to a wallet you control.

```bash
PAYER="<your-devnet-pubkey>"
curl -s -X POST https://musebook.trade/api/x402/batch/plan \
  -H 'content-type: application/json' \
  -d "{
    \"network\": \"solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1\",
    \"payer\": \"$PAYER\",
    \"payments\": [
      { \"payTo\": \"<recipient-1-pubkey>\", \"amount\": \"100000\" },
      { \"payTo\": \"<recipient-2-pubkey>\", \"amount\": \"100000\" },
      { \"payTo\": \"<recipient-3-pubkey>\", \"amount\": \"100000\" }
    ],
    \"ref\": \"my-agent\"
  }" | tee plan.json | jq '{planId, instructionCount, totalAmount, expiresAt}'
```

Rules (v0): 1–8 payments, single asset (the network's USDC), all amounts > 0.
The response includes `unsignedTx` (base64, **zero signatures**), the
`blockhash`, and an `expiresAt` — the plan is a quote, valid ~5 minutes.

> Note: recipients need an existing associated token account for USDC, or the
> transaction will fail on-chain. Fund/create ATAs out of band in v0.

## 3. Sign (in YOUR wallet — the facilitator never signs)

Decode `unsignedTx`, sign it with the payer key, re-encode. Example with a
local keypair (devnet only — never do this with mainnet funds on a shared box):

```bash
# node one-liner: sign plan.json's unsignedTx with keypair.json
node --input-type=module -e "
import { Keypair, VersionedTransaction } from '@solana/web3.js';
import { readFileSync, writeFileSync } from 'node:fs';
const plan = JSON.parse(readFileSync('plan.json', 'utf8'));
const kp = Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync('keypair.json', 'utf8'))));
const tx = VersionedTransaction.deserialize(Buffer.from(plan.unsignedTx, 'base64'));
tx.sign([kp]);
writeFileSync('signed.b64', Buffer.from(tx.serialize()).toString('base64'));
console.log('signed, payer =', kp.publicKey.toBase58());
"
```

## 4. Verify (safe — no broadcast)

```bash
SIGNED=$(cat signed.b64)
curl -s -X POST https://musebook.trade/api/x402/batch/verify \
  -H 'content-type: application/json' \
  -d @- <<EOF | jq .
{
  "network": "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
  "paymentHeader": "$SIGNED",
  "plan": $(cat plan.json | jq '{payer: .payer, items}')
}
EOF
```

Expected: `{"isValid": true, "payer": "<...>", "items": [...]}`.

The facilitator re-checks everything against the signed bytes: valid
signatures, **only** `TransferChecked` instructions for the exact USDC mint,
payer as sole authority, every planned payment present with amount ≥ required.
The plan echo is advisory — the bytes are the truth.

## 5. Settle (broadcasts — devnet first!)

```bash
curl -s -X POST https://musebook.trade/api/x402/batch/settle \
  -H 'content-type: application/json' \
  -d @- <<EOF | jq .
{
  "network": "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
  "paymentHeader": "$SIGNED",
  "plan": $(cat plan.json | jq '{payer: .payer, items}'),
  "ref": "my-agent"
}
EOF
```

Expected:

```json
{
  "success": true,
  "transaction": "<one signature>",
  "network": "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
  "payer": "<...>",
  "items": [
    { "payTo": "<recipient-1>", "amount": "100000", "status": "settled" },
    { "payTo": "<recipient-2>", "amount": "100000", "status": "settled" },
    { "payTo": "<recipient-3>", "amount": "100000", "status": "settled" }
  ],
  "receipt": "x402:receipt:<sig>"
}
```

One transaction fee. One confirmation wait. Three payments.

## 6. Check the public tape

```bash
curl -s "https://musebook.trade/api/x402/receipts?limit=5" | jq '.receipts[] | {id, batch, payer}'
curl -s https://musebook.trade/api/x402/pulse | jq '{settlements, batchSettlements, volumeBaseUnits}'
```

Your settlement is on the public m2m tape (unless you passed
`"private": true`), and your `ref` accrues volume credit on the pulse
leaderboard.

## Going further

- **Mainnet**: same flow with `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` and
  mainnet USDC `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`. Start tiny.
- **EVM (Base)**: sign an EIP-712 `TransferWithAuthorization` client-side and
  POST it to `/api/x402/batch/settle-multi` (see SPEC.md §2.4). The reference
  facilitator verifies EIP-712 + on-chain nonce state; settlement needs its
  relay key configured.
- **Run your own**: `npx muse-facilitator-kit init --chain solana --network
  mainnet && npx muse-facilitator-kit serve --port 8787` — then point the
  curl commands above at `localhost:8787`.
