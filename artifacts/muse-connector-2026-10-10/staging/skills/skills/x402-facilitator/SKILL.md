---
name: "x402-facilitator"
description: "Run your own x402 facilitator (Solana + EVM) with the x402m m2m meta protocol: single-signature batch settlement, facilitator discovery, receipts, and the machine-economy pulse. Non-custodial — payers sign, you verify and relay."
---

# x402 Facilitator

Deploy your own **x402 facilitator** — the machine-economy cashier that
verifies a payer signed a valid payment, then settles it on-chain. This
kit implements the **x402m** m2m meta protocol (`~/workspace/m2m-x402/SPEC.md`
on the reference install):

- **Batch settlement** — one payer, one signature, up to 8 USDC payments in
  a single Solana transaction (`x402m-batch-v0`)
- **EVM relay** — verify EIP-712/EIP-3009 authorizations, relay via
  `transferWithAuthorization` (`x402m-evm-relay-v0`)
- **Facilitator discovery** — `/.well-known/x402-facilitator` descriptor
- **Receipts + pulse** — a public m2m payment tape and 24h economy stats

**Non-custodial:** the facilitator verifies and relays. The payer signs.
It never holds user funds and never signs as authority.

## Quickstart (this skill ships the kit)

```bash
cd ~/workspace/skills/x402-facilitator
npm install

# Scaffold a facilitator in its own directory
mkdir ~/my-facilitator && cd ~/my-facilitator
node ~/workspace/skills/x402-facilitator/bin/cli.js init \
  --chain solana --network mainnet
# or: --chain evm|both   --network devnet

cp .env.example .env   # fill in RPC URLs / relay key as needed

# Serve it
node ~/workspace/skills/x402-facilitator/bin/cli.js serve --port 8787
```

Then:

```bash
curl localhost:8787/.well-known/x402-facilitator | jq .
curl localhost:8787/api/x402/batch/ping
```

Full kit docs: `KIT_README.md`. Client integration example:
`CLIENT_EXAMPLE.md`.

## How agents use a facilitator

1. **Discover** — `GET /.well-known/x402-facilitator` on any facilitator
   domain. No human in the loop.
2. **Plan** — `POST /api/x402/batch/plan` with `{network, payer,
   payments[]}`. Returns an **unsigned** transaction template + quote.
3. **Sign** — the payer signs in their own wallet (browser, mobile, or
   agent wallet). The facilitator never sees a private key.
4. **Settle** — `POST /api/x402/batch/settle` with the signed tx. The
   facilitator verifies and relays it on-chain, then publishes a receipt.

## EVM relay status

EVM relay is **experimental / verify-only** until a `FACILITATOR_EVM_KEY`
is configured in `.env` — without it, the EVM path verifies signatures
but does not relay. Never claim the EVM relay works end-to-end until a
real settlement test passes.

## Publishing to npm (optional)

The kit is publish-ready (`package.json` name `muse-facilitator-kit`).
Publishing is a human step — it needs the publisher's npm login:

```bash
cd ~/workspace/skills/x402-facilitator
npm login
npm publish --access public
```

Until then, installs use the copy shipped inside this skill (which is what
the installer tarball carries).

## Referral tracking

Pass `referral` / `ref` on plan/settle calls; the pulse endpoint reports
top referrers with volume. See `KIT_README.md`.
