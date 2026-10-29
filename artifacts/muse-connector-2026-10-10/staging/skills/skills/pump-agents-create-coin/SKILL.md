---
name: "pump-agents-create-coin"
description: "Create a pump.fun coin (plus optional initial buy) via the fun-block agent API. Returns an unsigned/base64 transaction the user's wallet co-signs — the agent never signs for the user."
---

# pump.agents Create Coin

Create a new pump.fun token, optionally with an initial buy, through the
preferred agent API. The API returns a transaction for the **user's wallet**
to finish signing.

## Endpoint

```
POST https://fun-block.pump.fun/agents/create-coin
```

Always request **base64 transaction encoding** in the request so the
returned transaction can be handed to the browser wallet.

## Request fields

- Token metadata: name, symbol, description, image (metadata upload per
  pump.fun flow)
- `initialBuySol` (optional): SOL amount for the creator's initial buy
- `cashback` (optional): enable creator cashback routing
- `mayhem` (optional): enable Mayhem mode
- `tokenizedAgentBps` / `buybackBps` (optional): tokenized-agent /
  buyback configuration
- `jitoOnly` (optional): submit via Jito-only for front-runner protection —
  never leak such a transaction through a public RPC

## Signing rule

- The API returns an **unsigned or partially-signed** transaction.
- The **user wallet co-signs** in the browser. The agent must **not** sign
  for the user and must never request or handle the user's private key.

## Verification status (2026-09-19)

- Host `https://fun-block.pump.fun/` → HTTP 200 (live).
- `GET /agents/create-coin` → HTTP 404 (expected: POST-only endpoint).
- The full POST create-coin flow has **not** been live-tested end to end;
  treat field names as the documented contract and validate against a
  dry-run before any user-facing launch.

## Safety

- Coin creation is a user-approved action with exact terms confirmed first.
- Browser-first signing only; no local keypairs.
