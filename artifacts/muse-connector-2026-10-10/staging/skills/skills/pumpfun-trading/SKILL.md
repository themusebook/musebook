---
name: pumpfun-trading
description: Quick Pump.fun trading shortcut for buy/sell flow selection, bonding curve versus AMM state checks, slippage handling, risk controls, and SDK trade instruction building.
---

# Pump.fun Trading

Execute buy and sell trades on the Pump.fun protocol using the native Pump SDK. Supports both bonding curve trading (pre-graduation) and AMM pool trading (post-graduation).

## Prerequisites

- Funded Solana wallet via `nanosolana birth`
- `HELIUS_RPC_URL` configured
- Understanding of bonding curve mechanics

## Trading Flow

> **Step 0 — plan first.** Every buy, sell, and creator-fee claim starts with
> `bin/pump_plan.py`, which builds a DRY-RUN plan JSON (signs nothing,
> broadcasts nothing, fetches nothing) and prints the exact chat-approval
> summary to paste to the user. Chat approval of the exact terms is step 1;
> SDK instruction build comes only after approval.

### 1. Check Token State

Before trading, always check if the token is on the bonding curve or has graduated:

```typescript
const sdk = new OnlinePumpSdk(connection);
const summary = await sdk.fetchBondingCurveSummary(mint);

if (summary.isGraduated) {
  // Use AMM trading instructions
} else {
  // Use bonding curve trading instructions
}
```

### 2. Buy on Bonding Curve

```typescript
import { OnlinePumpSdk, getBuyTokenAmountFromSolAmount } from "nanosolana";
import BN from "bn.js";

const sdk = new OnlinePumpSdk(connection);

// Fetch state
const [buyState, global, feeConfig] = await Promise.all([
  sdk.fetchBuyState(mint, user),
  sdk.fetchGlobal(),
  sdk.fetchFeeConfig(),
]);

// Calculate expected tokens
const solAmount = new BN(100_000_000); // 0.1 SOL
const expectedTokens = getBuyTokenAmountFromSolAmount({
  global, feeConfig,
  mintSupply: buyState.bondingCurve.tokenTotalSupply,
  bondingCurve: buyState.bondingCurve,
  amount: solAmount,
});

// Build instructions
const buyIxs = await sdk.buyInstructions({
  ...buyState, mint, user,
  amount: expectedTokens,
  solAmount,
  slippage: 0.05, // 5%
});
```

### 3. Sell on Bonding Curve

```typescript
import { getSellSolAmountFromTokenAmount } from "nanosolana";

const [sellState, global, feeConfig] = await Promise.all([
  sdk.fetchSellState(mint, user),
  sdk.fetchGlobal(),
  sdk.fetchFeeConfig(),
]);

const tokenAmount = new BN(1_000_000_000);
const expectedSol = getSellSolAmountFromTokenAmount({
  global, feeConfig,
  mintSupply: sellState.bondingCurve.tokenTotalSupply,
  bondingCurve: sellState.bondingCurve,
  amount: tokenAmount,
});

const sellIxs = await sdk.sellInstructions({
  ...sellState, mint, user,
  amount: tokenAmount,
  solAmount: expectedSol,
  slippage: 0.05,
});
```

## Risk Management

| Control | Value |
|---------|-------|
| Always use slippage | 3-5% recommended |
| Check `bondingCurve.complete` | Before trading |
| Use `BN` for all amounts | Never use JS `number` |
| Max position per trade | Follow Kelly Criterion |
| Circuit breaker | -10% daily → pause 24h |

## Integration with Swarm

Swarm agents with the `sniper`, `momentum`, and `graduation` roles use this skill automatically via the OODA trading loop.

## Live execution policy

Every buy, sell, and creator-fee claim follows this exact sequence:

1. **Prepare** — run `bin/pump_plan.py` to build a dry-run plan JSON. It signs
   nothing, broadcasts nothing, and fetches nothing from the network.
2. **Approve** — the user approves the EXACT terms in chat: mint, side, amount,
   slippage, max cost. No approval, no further steps.
3. **Sign** — the user signs in their own browser wallet. No local keypairs for
   pump.fun trading: the standing rule is that all signing happens in the
   user's browser unless the user explicitly approves a named, scoped local-key
   exception — and no such exception exists for pump.fun.
4. **Submit** — broadcast the user-signed transaction.
5. **Confirm** — verify on-chain, then report the receipt (signature, amounts).

**Creator fee claims are creator-only.** Only the wallet that created a token
can make a valid fee claim. `pump_plan.py --side claim-fees` requires
`--creator`, and the plan is only valid when the browser signing wallet IS that
creator. If the user did not create the token, refuse to prepare or submit a
claim and explain why: the on-chain claim instruction is only valid for the
creator signer, so there is nothing to execute.

**Quote enrichment is a follow-up.** `pump_plan.py` v1 is offline: it validates
inputs and records policy fields but fetches no quotes. Enriching plans with
live quotes (Helius/RPC) is planned, not yet built.

Market data and plans are research/organization only — never buy/sell advice.
