---
name: "pump-agents-swap"
description: "Buy/sell pump.fun tokens (bonding curve or graduated Pump AMM) via the fun-block agent API. Slippage protection, optional Jito-only submission, user wallet signs."
---

# pump.agents Swap

Buy or sell pump.fun tokens through the preferred agent API, covering both
bonding-curve tokens and graduated Pump AMM tokens. The API returns a
transaction for the **user's wallet** to sign.

## Endpoint

```
POST https://fun-block.pump.fun/agents/swap
```

Always request **base64 transaction encoding**.

## Request fields

- `mint`: token mint to trade
- `side`: `buy` | `sell`
- `amountSol` / `amountTokens`: size (quote first)
- `slippageBps`: slippage protection (required on every trade)
- `jitoOnly` (optional): Jito-only submission for front-runner protection —
  never leak such a transaction through a public RPC

## Market state

Check whether the token is still on the bonding curve or has graduated to
the Pump AMM before building the swap — routing differs. Quote the trade
first and show the user the expected output before asking for approval.

## Signing rule

- Returns **unsigned/partially-signed** transaction; the user wallet
  co-signs in the browser. The agent never signs for the user.

## Verification status (2026-09-19)

- Host `https://fun-block.pump.fun/` → HTTP 200 (live).
- `GET /agents/swap` → HTTP 404 (expected: POST-only endpoint).
- Full POST swap flow **not** live-tested end to end; validate with a
  dry-run/quote before any live trade.

## Safety

- Every swap needs the user's fresh approval of exact terms (mint, side,
  size, slippage). Browser-first signing only.
