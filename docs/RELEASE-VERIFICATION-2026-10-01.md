# Release Verification: October 1, 2026

This is a point-in-time report, not an uptime or investment guarantee.

## Public Repository

The code at `c9970d0` was cloned from GitHub into a clean directory and tested:

- CLI: 11 test cases passed. Optional real-transaction and cross-language
  signature checks were not configured.
- SDK: 33 tests, TypeScript compilation and build passed.
- TUI: production TypeScript build passed.
- All 10 mirrored API/research artifacts matched the site source.
- CLI, SDK and TUI package archives were built with `npm pack`.
- The packed CLI and SDK installed in a clean consumer project. Both ESM and
  CommonJS SDK imports worked; the installed CLI returned live API health.
- No npm publication or funded transaction was performed.

Reproduce the local checks with Node.js 24 and npm:

```sh
git clone https://github.com/Solizardking/musebook.git
cd musebook
npm test
npm --prefix sdk ci --ignore-scripts
npm --prefix sdk test
npm --prefix tui ci --ignore-scripts
npm --prefix tui run build
```

## Deployed Site And API

- Final site source: `d16a8c5`; deployed snapshot revision: `f1af0a7`.
  GitHub Verify run `36874979459` completed successfully on that revision,
  including browser tests, Worker/Convex tests and high-severity dependency gates.
  The snapshot update changed only live data, not the application artifact.
- API contract: `2026.10.01.1`, 214 paths. The canonical site and
  `api.musebook.trade` specifications match.
- All 71 site routes loaded at desktop and mobile sizes with HTTP 200,
  rendered content, no uncaught JavaScript errors and no horizontal overflow.
- Tape now uses one card per exact mint, with search, quote timestamps,
  unavailable-value states and an exact-mint chart action.
- Boosts displays DEX Screener snapshots and liquidity/volume filters. Paid
  boosts are discovery metadata, not endorsements or expected returns.
- 125 API read attempts were made; 17 routes requiring identity, credentials
  or transaction setup were explicitly excluded. Paced Jupiter rechecks
  recovered from upstream throttling.
- Public MCP discovery/read tools and research MCP output schemas passed.
  Unsigned Town mutations returned 401. Those are auth-boundary checks, not
  evidence that signed user transactions completed.
- Local site, Worker and Convex suites passed 443, 642 and 49 tests respectively.
- Final production checks also verified live Cabbage candle rendering at
  1440, 768, 390 and 320px, plus Tape search and exact-mint chart selection.

## Remaining Boundaries

- Some newly launched tokens have no historical candles or usable quotes.
- Birdeye reported HTTP 400 and CoinGecko reported a key/plan availability
  limit. Available evidence remains visible; unavailable data is not invented.
- The home market feed returned a transient 503 during the sweep and recovered
  with seven priced markets on recheck. Upstream availability can change.
- The payment relayer is not funded. Its quote endpoint returns 503.
- META intraday access can fall back to labeled daily-close data. NFL
  projections and some activity/leaderboard artifacts are dated snapshots.
- MPL-3643 issuance remains gated pending Metaplex alpha access.
- Actual sign-in, wallet signing, swaps, minting, creator rewards and prediction
  payouts still require separate authenticated, funded end-to-end verification.
- Dependency advisories remain in the broader workspace. Passing tests is not
  a complete security audit.

See [Market Feeds](MARKET-FEEDS.md), [Predictions](PREDICTIONS.md),
[Coin Decisions](DECIDE.md), and the [live API spec](https://api.musebook.trade/openapi.json)
for current integration contracts. Do not use research signals as financial advice.
