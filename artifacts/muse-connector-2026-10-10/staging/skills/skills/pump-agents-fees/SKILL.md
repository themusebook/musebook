---
name: "pump-agents-fees"
description: "Inspect pump.fun creator-fee destinations, collect creator fees/cashback, and manage shared-fee distribution configs via the fun-block agent API."
---

# pump.agents Coin Fees

Inspect where creator fees go, collect direct creator fees or cashback, and
create/update shared-fee distribution configs.

## Endpoints

```
POST https://fun-block.pump.fun/agents/collect-fees
POST https://fun-block.pump.fun/agents/sharing-config
```

Always request **base64 transaction encoding** for any returned transaction.

## Capabilities

- **Inspect**: read the creator-fee destination for a coin before collecting.
- **Collect**: collect direct creator fees, or collect cashback, to the
  creator wallet.
- **Distribute**: distribute shared fees to configured recipients.
- **Configure**: create or update a fee-sharing config (recipients + BPS
  splits).

## Signing rule

- Any transaction returned is **unsigned/partially-signed**; the user wallet
  co-signs in the browser. The agent never signs for the user.

## Verification status (2026-09-19)

- Host `https://fun-block.pump.fun/` → HTTP 200 (live).
- `GET /agents/collect-fees` → HTTP 404, `GET /agents/sharing-config` →
  HTTP 404 (expected: POST-only endpoints).
- Collect/sharing flows **not** live-tested end to end; validate request
  shapes with a dry-run first.

## Safety

- Fee collection/distribution moves funds — requires the user's fresh
  approval of exact terms (coin, amounts, recipients). Browser-first
  signing only.
