---
name: "pump-agents-payments"
description: "Tokenized-agent payments via @pump-fun/agent-payments-sdk: build SOL/USDC invoices the user signs; server verifies on-chain before delivering service. Duplicate-safe via Invoice ID PDA."
---

# pump.agents Tokenized-Agent Payments

Accept payments for agent services using the official
`@pump-fun/agent-payments-sdk`. The agent builds an invoice; the **user
signs the payment**; the server verifies the payment on-chain before
delivering the service.

## Package

```
npm install @pump-fun/agent-payments-sdk
```

Verified on the npm registry 2026-09-19: version **3.0.3** exists.

## Flow

1. Agent builds an invoice for a SOL or USDC amount (service, price, payer).
2. Invoice references an **Invoice ID PDA** — duplicate protection: the same
   invoice cannot be paid twice.
3. User reviews and **signs the payment in their wallet** (browser-first).
4. Server verifies the invoice payment **on-chain** before delivering the
   service — never deliver on an unverified claim.

## Signing rule

- The agent builds the invoice; it never signs or submits the user's
  payment. The user wallet signs.

## Verification status (2026-09-19)

- npm package `@pump-fun/agent-payments-sdk@3.0.3` confirmed on registry.
- Invoice build → user sign → on-chain verify flow documented from the
  SDK contract; not live-tested end to end in this workspace.

## Safety

- Payment amounts and the service being purchased need the user's explicit
  approval first. No auto-charging.
