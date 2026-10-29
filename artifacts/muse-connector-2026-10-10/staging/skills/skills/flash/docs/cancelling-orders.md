# Cancelling Orders

> How to cancel an open Flash order by signing a cancel message with the funder wallet.

Cancel any open order with `POST /orders/{orderId}/cancel`. Like placing an order, cancelling one requires a **wallet signature** in addition to your API key — but where an order signs the payload returned by the quote, a cancel signs a short plaintext message you construct yourself. The cancel signature is offchain and gasless; no transaction is sent.

## The cancel message

Construct this exact UTF-8 string, substituting the `orderId` returned when the order was placed:

```text
Definitive Flash v1 — Cancel Order
Order: <orderId>
```

That is one string with a single newline:

```ts
const cancelMessage = `Definitive Flash v1 — Cancel Order\nOrder: ${orderId}`;
```

- The separator after `v1` is an **em dash** (`—`, U+2014), not a hyphen.
- The line break is a single `\n`.
- `<orderId>` is the order's UUID exactly as returned by `POST /order`.

Send the exact string you signed back as `cancelMessage` in the request body.

## Signing

Sign with the **funder wallet** — the same wallet that signed the order.

| Chain  | Scheme                                        | `userSignature` format |
| ------ | --------------------------------------------- | ---------------------- |
| EVM    | EIP-191 `personal_sign` over the message bytes | 65 bytes, `0x`-hex    |
| Solana | Ed25519 over the message bytes                | 64 bytes, base58       |

EVM: verified onchain against the funder address using ERC-1271 with ERC-6492 (EOAs, deployed and counterfactual smart accounts all work).

## What a cancel does

- Takes effect immediately; order removed from execution queue, status `ORDER_STATUS_CANCELLED` with `closeReason` `REASON_USER_REQUESTED`; `update` fires on the Orders WebSocket.
- **Partial fills are kept.** Cancelling a partially filled order stops remaining execution; settled slices are final.
- **Bracket pair is cancelled separately.** Cancelling an entry order does not cancel its attached bracket pair; cancel each by its own `orderId`.
- **Token approval is untouched.** Cancel removes the order, not the onchain approval/delegate. Revoke onchain to remove spending authority entirely.
- **Idempotent.** Cancelling an already-cancelled order returns `200`.

## Which orders can be cancelled

`ORDER_STATUS_PENDING`, `ORDER_STATUS_ACCEPTED`, or `ORDER_STATUS_PARTIALLY_FILLED` can be cancelled. Terminal statuses (`FILLED`, `REJECTED`, `TERMINATED`) return `422` — except already-cancelled, which returns `200`.

Cancel/fill race: if the order fills first, cancel returns `422` with `order already filled` — treat as executed, not a failure to retry.

## Solana example

```ts
import { Keypair } from "@solana/web3.js";
import nacl from "tweetnacl";
import bs58 from "bs58";

const orderId = "..."; // from POST /order
const cancelMessage = `Definitive Flash v1 — Cancel Order\nOrder: ${orderId}`;
const signature = nacl.sign.detached(new TextEncoder().encode(cancelMessage), funder.secretKey);
const userSignature = bs58.encode(signature);

const res = await fetch(`${BASE_URL}/orders/${orderId}/cancel`, {
  method: "POST",
  headers: { "content-type": "application/json", "x-definitive-api-key": API_KEY },
  body: JSON.stringify({ cancelMessage, userSignature }),
}).then((r) => r.json());
// { ok: true }
```
