---
name: imperial-twap-execution
description: TWAP/DCA execution guidance for Imperial: slice planning, native DCA order types, venue pinning, profile budgeting, and durable-runner requirements.
---

# Imperial TWAP Execution

Parent skill `imperial` holds the full API reference.

Imperial exposes order primitives, not a first-class TWAP runner in this repo.
Two implementation paths:

## A. Native DCA order types (single request, server-managed)

The API has first-class DCA families — prefer these over hand-rolled slice
loops when the shape fits:

- 9 Dca (`extraData.dcaStartPrice`, `dcaEndPrice`, `dcaNumLegs`)
- 12 DcaClose (`dcaCloseStartPrice`, `dcaCloseEndPrice`, `dcaCloseNumLegs`)
- 13 DcaTimeClose (`dcaCloseIntervalSeconds`, `dcaCloseNumLegs`)
- 14 DcaRatchetClose (`dcaCloseNumLegs`, `dcaCloseRatchetSize`)
- 15 DcaTime (`dcaIntervalSeconds`, `dcaNumLegs`)
- 16 DcaRatchet (`dcaNumLegs`, `dcaCloseRatchetSize`)

All prices in `extraData` are oracle scale (×1e9). Pairs (5) and Armada (7)
reject the DCA family — pin DCA flow to Jupiter (0), Phoenix (2), or GMTrade (3).

## B. Client-driven slices (durable runner required)

For TWAP shapes the native types don't cover (custom schedules, cross-venue
hedged TWAP, conditional logic):

- Define: slice count, interval, side, notional per slice, venue pinning
  (or route-based), profile budget, total slippage envelope.
- Decide venue pinning up front: Phoenix default; `/route` per slice if the
  book/funding moves materially between slices.
- A durable worker must own the loop and persist between slices: slices
  executed, fills, remaining notional, last slice timestamp, failure count.
- Webhook caveat: the Telegram webhook can create a TWAP plan but must not
  masquerade as the runner. Long-lived slice execution needs a real runner
  with persisted state (cron + state file, or a dedicated worker).

## Risk notes for both paths

- Preflight the first slice's exact body; re-preflight if venue or size changes.
- Slice notional against per-profile balances — profiles don't share funds.
- On a Phoenix cross seat, slices draw on seat-wide free margin; monitor
  `/phoenix/margin-account`, not per-leg collateral.
- Track fills via `/ws` (tradeEvents/positionState) or poll `/orders`;
  placement ≠ fill for resting slices.
