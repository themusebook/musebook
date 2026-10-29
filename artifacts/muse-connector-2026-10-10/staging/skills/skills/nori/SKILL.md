---
name: "nori"
description: "Use Nori when the user asks for Nori, the Metaplex Foundation service agent, or pay-as-you-go LLM inference, image generation, or Solana RPC (including DAS)."
---

# Nori

## Purpose
Nori is a pay-as-you-go service agent operated by the Metaplex Foundation. It
exposes three services plus an A2A interface — no subscription, you are billed
per successful call.

**No live NORI_URL is verified.** Treat `NORI_URL` as user-configured. The
first step with any Nori endpoint is always `discover` (below): fetch the
agent card and the rate card, and verify the `serviceExecutiveAddress` out of
band before any delegation is even discussed.

## Services

| Service | Endpoint | Notes |
|---|---|---|
| chat.completion | `POST {NORI_URL}/v1/chat/completions` | OpenAI-compatible. Models addressed as `<provider>/<model>`, e.g. `anthropic/claude-sonnet-4-6`, `openai/gpt-5.4`, `google/gemini-2.5-flash`. Tool calls supported. Non-streaming. |
| image.generation | `POST {NORI_URL}/v1/images/generations` | Model `openai/gpt-image-1`. Flat per-image price. |
| solana.rpc | `POST {NORI_URL}/v1/solana/rpc` | Transparent JSON-RPC pass-through **including DAS methods** (`getAsset`, `getAssetsByOwner`, ...). Flat per-call price. |
| A2A | `POST {NORI_URL}/a2a` | JSON-RPC `message/send` with `{skill, input}` inside a `DataPart`. (`message/sendStream` returns 501.) |

Discovery endpoints:

- `GET {NORI_URL}/.well-known/agent-card.json` — agent card (capabilities, `serviceExecutiveAddress`)
- `GET {NORI_URL}/rate-card` — per-service prices
- `GET {NORI_URL}/v1/models` — model directory

## Tooling
`bin/nori.py` is the helper. It uses `urllib` (respects `https_proxy`).

- `nori.py discover --url <NORI_URL>` — fetches the agent card + rate card and
  prints a summary (services, models, prices, `serviceExecutiveAddress`).
  Read-only; this is always step one.
- `nori.py call chat|image|rpc --url <NORI_URL> ...` — **dry-run only**: prints
  the exact `curl` for the call and exits. It never sends the request, never
  pays, never signs. Copy the curl, review the price on the rate card, and run
  it yourself after the user approves the exact spend.

Ready-to-run TypeScript patterns live in `templates/`:

- `templates/inference-agent.ts` — OpenAI-compatible client at `{NORI_URL}/v1`
  with a tool-call loop
- `templates/artwork-agent.ts` — image generation
- `templates/portfolio-analyzer.ts` — `solana.rpc` `getBalance` + DAS
  `getAssetsByOwner`
- `templates/a2a-caller.ts` — A2A `message/send` envelope

## Billing
Charge-on-success. Two payment rails:

- **delegate-pay** — obtain a bearer token from `POST {NORI_URL}/auth/handshake`
  (15-minute expiry). Presenting it grants fund-transfer authority over the
  agent's Asset Signer PDA, so the service can pull payment on success.
- **x402 v2 fallback** — the first call returns `402` with payment
  requirements; you pay and retry with the payment proof attached.

### Paying Nori over x402 via the Musebook facilitator

When Nori answers a call with HTTP `402`, the response body carries x402
payment requirements (an `accepts` entry: `scheme`, `network`, `payTo`,
`asset`, `maxAmountRequired`). Instead of running your own facilitator, you
can route the x402 payment through the **Musebook facilitator** — a no-custody
Cloudflare Worker that never holds keys and never touches your funds. It only
**verifies** your signed payment off-chain and **settles** (broadcasts) it
on-chain.

Supported kinds (live — verify anytime with
`GET https://musebook.trade/api/x402/supported`):

| scheme | network | x402 version |
| --- | --- | --- |
| `exact` | `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` (mainnet USDC `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`) | v1 |
| `exact` | `solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` (devnet USDC `4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU`) | v1 |
| `upto`  | `solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` (devnet) | v2 |

Payment flow (client-side — **no facilitator keypair or credential needed**,
point your x402 client at the facilitator URL):

1. Your x402 client builds the payment payload from Nori's 402 requirements
   (a signed exact-scheme USDC transfer transaction to `payTo`). Signing
   happens per standing policy: browser wallet for the user, or a
   user-approved scoped local wallet — never improvise.
2. **Verify off-chain** (cached ~60s, skips an RPC round trip on repeats):
   `POST https://musebook.trade/api/x402/verify` with the x402 payment
   payload (the facilitator expects the payment requirements plus the signed
   transaction, base64). Returns `{ isValid: true, payer }` or an
   `invalidReason` such as `wrong_asset`, `insufficient_amount`,
   `wrong_recipient`, or `invalid_signature`. Never retry a payment that
   fails verification.
3. **Settle on-chain**:
   `POST https://musebook.trade/api/x402/settle` with the same payload.
   The facilitator re-uses a fresh verify verdict (5-min cache) or verifies
   again, broadcasts the signed transaction, waits for confirmation (up to
   ~20s), and returns the on-chain transaction signature. A 402 from this
   endpoint means verification failed — do not rebroadcast.
4. Retry the original Nori call with the payment proof attached per the x402
   spec.

`POST https://musebook.trade/api/x402/reconcile` exists for on-demand
reconciliation of pending settlements, but a cron already does this every
5 minutes — you normally don't need it.

**Policy reminders (hard):** every payment still needs the user's explicit
approval of the exact spend in chat before any signing or sending; the
facilitator cannot waive that. Read-only here — this skill documents the
flow; it never signs, pays, or funds anything.

## Auth
No Nori credential is stored by this skill. Do not ask the user to paste a
token in chat, set a secret environment variable, or write an auth file.
Payment for Nori calls happens per call (delegate-pay bearer or x402), always
with the user's explicit approval of the exact spend first.

## Security warnings — read before touching delegation
1. **Verify `serviceExecutiveAddress` out of band** (compare it against a
   Metaplex-published value through an independent channel) before any
   delegation. A bearer token that grants fund-transfer authority over your
   agent's Asset Signer PDA is only as trustworthy as the address it delegates
   to.
2. Delegation is a **separate, explicit flow**: the user approves the exact
   service, the exact maximum spend, and the expiry, in chat, before any
   handshake is performed. Approval is per session — a 15-minute bearer token
   is never reused past its purpose.
3. If the agent card or rate card looks wrong (unknown executive address,
   prices that changed without notice, TLS errors), stop and report it. Do not
   proceed to payment.

## Operating Rules
1. Use this skill when the user asks for Nori or the Metaplex Foundation
   service agent.
2. **Hard constraints — no exceptions:** no spending, no signing, no wallet
   funding, no Nori delegation, no token launches, no irreversible actions.
   This skill is read-only discovery, code, and docs.
3. Delegation is documented as an explicit user-approved flow with warnings
   only — it is never implemented or executed by this skill's tooling.
4. Always run `discover` against a new `NORI_URL` before anything else.
5. `nori.py call` prints curl; it never executes. A 402 response to a manual
   call means payment is required — stop and get the user's approval of the
   exact price before paying.
6. Never print, log, or persist bearer tokens or payment proofs.
