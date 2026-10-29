---
name: birdeye
version: 1.2.0
description: Read BirdEye Solana token overview data through read-only Musebook OAuth, with exact mint validation and explicit provider availability.
---

# BirdEye for Muse

Default connection: OAuth 2.1 at `https://musebook.trade/mcp-auth`, scope `read`, PKCE S256. Submitted tool: `birdeye_token_overview`. Input: `{ "address": "So11111111111111111111111111111111111111112" }`. Output: source `birdeye`, chain `solana`, exact address, `retrieved_at`, and a bounded `data` object containing available price, market cap, liquidity, holder and 30-minute activity fields. Exact schemas are in `docs/tools.json`.

The server uses its configured BirdEye provider credential for this OAuth tool. It does not retrieve a user's BirdEye API key. No provider key is required from the Muse user, but server plan and compute allowance limit availability. `birdeye_not_configured`, `birdeye_plan_unavailable`, `birdeye_rate_limited`, `birdeye_quota_exhausted` and `birdeye_unavailable` are errors, never data. Do not retry exhausted quota or silently use another provider.

Example: "Show this Solana mint's price, market cap, liquidity, holders and last 30 minutes of activity." Return available fields, source, retrieval time and missing fields. Do not interpolate a 15-minute period, make recommendations or place trades.

Classification: Read. Sensitive: false. Scope: `read`. Side effects: provider usage accounting and routine service access records only; no user account, wallet or order changes. Respect Muse's Allow once, Always allow and Deny controls.

Optional direct access uses the separately connected `custom.birdeye` credential through Muse's credential surrogate helper. `birdeye.py GET '/defi/token_overview?address=<mint>' --header 'x-chain: solana'` sends only the stored surrogate to `public-api.birdeye.so`. This CLI requires Muse's credential helper; it is not a standalone OAuth client. Never paste or store a raw key. All methods other than GET and all redirects are rejected. The submitted OAuth tool does not depend on this CLI.

See `docs/connector-submission.md` for restrictions, data processing and reviewer instructions.
