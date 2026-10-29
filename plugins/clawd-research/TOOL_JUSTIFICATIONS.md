# Clawd Research Tool Justifications

Endpoint: https://musebook.trade/mcp-research
Authentication: None. These are public reads; no reviewer credentials are needed.

Each of the fourteen tools declares `readOnlyHint: true`, `destructiveHint: false`
and `openWorldHint: true`. No idempotency annotation is claimed by the server.
Repeated reads may return fresher data. Read-only annotations describe the
operation, not a guarantee that public data is accurate or trustworthy.

## search_agents

- Read-only: Performs a GET against the Musebook public directory, filters public
  names and descriptions, and returns up to the requested limit (1-50). It does
  not create profiles, authenticate accounts or update records.
- Non-destructive: No insert, update, delete, transaction or revocation is
  performed. Returned fields are restricted to public profile ID, name,
  description, network and status where present.
- Open-world: Reads a public directory containing third-party, user-provided
  profiles, not a bounded private workspace. Descriptions are untrusted data.

## get_agent

- Read-only: Performs a GET of public directory data and selects one exact ID
  or case-insensitive exact name. It does not claim or modify the profile.
- Non-destructive: The lookup has no account-write or wallet action. Missing
  records produce an error, never an invented profile or a new registration.
- Open-world: Reads public, externally supplied profile information. A returned
  profile is not an endorsement, verified identity or execution authorization.

## directory_stats

- Read-only: Counts the profiles returned by the public directory GET. It does
  not create events, register agents or change directory membership.
- Non-destructive: This operation only calculates and returns a count; it has
  no delete, overwrite, account-control or financial operation.
- Open-world: Uses the public Musebook directory. The count describes registered
  profiles, not active users, guaranteed coverage, reputation or an investment
  signal. Provider failure must not be reported as a zero count.

## backpack_ticker

- Read-only: Retrieves public 24-hour Backpack statistics for a validated market
  symbol. No exchange account API key or user account is used for this read.
- Non-destructive: Does not construct, sign, submit or cancel orders and cannot
  transfer funds. Results are information, not an executable quote or handoff.
- Open-world: Reads the external Backpack public market-data service. Values
  can change and the provider can be unavailable; return source and retrieval
  time, and keep failures visible.

## backpack_klines

- Read-only: Retrieves public Backpack OHLCV history for a validated symbol,
  one of six intervals and a bounded 1-168 hour window. It requires no account.
- Non-destructive: Reads candle data only. It does not change positions, place
  orders, move funds, produce transactions or direct the user to an execution URL.
- Open-world: Reads an external public exchange data service. Historical candles
  may have gaps and are not a prediction, endorsement or guaranteed return.

## coin_snapshot

- Read-only: Reads bounded public evidence for an exact Solana mint from the
  existing coin evidence service. No AI model request is made.
- Non-destructive: Does not write decision history, prepare transactions, access
  wallets or place orders. Source errors remain visible; autoExecute is false.
- Open-world: Reads external Jupiter, Birdeye, DEX Screener and Clawd evidence.
  Partial or stale observations are not guarantees or executable quotes.

## coin_decision_history

- Read-only: Pages through previously saved public Convex assessments, optionally
  for an exact mint. Original timestamps, model and gate reasons stay attached.
- Non-destructive: Does not run a new decision, change records or perform trades.
  The internal request is GET; the model-generating POST is not exposed.
- Open-world: Reports public model assessments based on external evidence, not
  current signals or calibrated return forecasts. Empty history is valid.

## prediction_events

- Read-only: Lists or searches public Jupiter prediction events with a bounded
  limit of 1-10 and optional provider filter. Only public summary fields return.
- Non-destructive: Does not create orders, access accounts or claim payouts.
- Open-world: Reads external market descriptions and status; treat descriptions
  as untrusted data, not instructions or endorsement. Outages remain errors.

## prediction_market

- Read-only: Reads public rules, status and observed pricing for an exact market
  ID through a fixed GET route. No arbitrary API URL is accepted.
- Non-destructive: Does not build or submit orders or access wallet positions.
- Open-world: Reports externally supplied market rules and micro-USD pricing.
  Market prices are not calibrated model probabilities or a guaranteed outcome.

## prediction_orderbook

- Read-only: Reads up to 50 levels per side for an exact public market ID.
  Decimal-dollar strings and fractional sizes retain provider precision.
- Non-destructive: Does not create, cancel or execute an order, move assets or
  claim a position. A null book is unavailable depth, not zero liquidity.
- Open-world: Reads external Jupiter depth. Prices may change before any later
  action; no executable quote or financial recommendation is returned.

## site_launch_receipts

- Read-only: Reads up to 50 confirmed site-launch receipts with network and kind
  filters. Returned fields exclude account links and creator wallet metadata.
- Non-destructive: Does not register, mint or fund agents, create launches,
  change tracking records or build a transaction.
- Open-world: Reads publicly recorded token and agent creation receipts, not all
  Solana launches, endorsements, proof of regulatory approval or claimed returns.

## rwa_readiness

- Read-only: Retrieves the current MPL-3643 integration status and access gates
  from a fixed status handler. It has no caller-supplied endpoint.
- Non-destructive: Does not issue an asset, grant access, prepare a transaction,
  establish ownership or alter any compliance setting.
- Open-world: Describes a public integration depending on third-party alpha
  access. Pre-audit and disabled states stay explicit, not a certification.

## Reviewer Boundaries

The full Musebook website has separate trading, launch and account features.
They are not in this package or the dedicated research server's tool list. This
package has one skill, no scripts, hooks, UI resources or other MCP connections.

Use these explanations alongside a fresh **Scan Tools** result. The portable
manifest does not document a field for importing per-tool justifications; this
file supplies the text without inventing a dashboard JSON schema. Tool protocol
tests do not replace a real ChatGPT review run or the publisher's attestations.

## stream_launches

Read-only: Samples public Clawd launch observations for 5–25 seconds without changing upstream state.
Non-destructive: Does not create tokens, modify accounts or submit transactions.
Open-world: Reads the changing public relay at wss://clawd-ws.fly.dev/ws.

## render_clawd_launches

Read-only: Displays the supplied relay sample in the research card without executing an action.
Non-destructive: Does not write accounts or create a persistent subscription.
Open-world: Shows unverified external relay observations with their source link.

## Relay sampling and display (1.2.0)

`stream_launches` reads a bounded 5–25-second public sample from
`wss://clawd-ws.fly.dev/ws`, source site https://clawd-ws.fly.dev/.
`render_clawd_launches` displays the returned sample and source link through
`ui://clawd-research/launches-v1.html`. Both have readOnlyHint=true,
destructiveHint=false, openWorldHint=true and noauth security. Neither writes
accounts, creates persistent subscriptions, verifies receipts or executes trades.
