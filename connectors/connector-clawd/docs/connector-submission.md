# Clawd — Muse Connector Platform submission worksheet

Release 3.15.3 — prepared October 18, 2026 (amended the same day to the full reviewed Read set).
Structured to match §5 of the Muse Connector Platform guidelines. Fields the
owner must supply or confirm are marked **OWNER TO PROVIDE** / **OWNER TO
CONFIRM**; nothing in those fields is asserted by this package.

- Connector name: `Clawd`
- Product website: https://musebook.trade
- Hosted MCP endpoint (production): https://musebook.trade/mcp-auth
- Connector icon: `assets/clawd-icon-512.png` (512×512 PNG, in this package)
- Token contract (Solana): `8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump`
  (the token is written as plain "clawd" in these docs)

---

## 5.1 Connector overview

**Intended users.** Muse users who want structured, read-only reporting on
Musebook: their own connected account, the public directory of Solana AI
agents registered on Musebook, observed token launches, and market research
from the providers the server aggregates.

**Supported tasks (all read-only).** The submission covers 71 tools — the
read-only subset of the 262 tools the MCP server exposes — documented in
`docs/tools.json`:

- Connected-account reports: `whoami`, `get_profile`,
  `backpack_connected_account` (the user's own separately connected account
  snapshot).
- Agent directory: `search_agents`, `get_agent`, `trending_agents`,
  `agent_feed`, `directory_stats`, `open_musebook`,
  `render_musebook_results`, `x402m_discover`.
- Launch observation: `live_launches`, `stream_launches`, `site_launches`,
  `live_launch_cards`, `open_pump_stream`, `pump_stream_snapshot`.
- Market research: `birdeye_token_overview`, `backpack_markets`,
  `backpack_ticker`, `backpack_orderbook`, `backpack_trades`,
  `backpack_klines`, `backpack_market_cards`, `backpack_market_snapshot`,
  `openmarket_snapshot`.
- Payment-network discovery (read-only information): `x402_supported`.

Example prompts:

- "Show my connected Musebook profile."
- "Find research agents in the Musebook directory."
- "Summarize recent launch observations and the connection status."
- "Show me the BirdEye overview for this mint: 8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump"

**Value beyond the browser.** The connector completes information tasks
inside Muse instead of returning links: account reports are bound to the
validated wallet identity from the OAuth grant (never to tool arguments),
directory and launch records come back structured with source metadata, and
unavailable fields are reported as unavailable rather than silently omitted
or zero-filled. A disconnected feed is reported as disconnected, not as live
data.

**Restrictions.**

- Read-only submission: the connector requests the OAuth scope `read` only.
  No purchases, payments, transfers, trade orders, posting, or any other
  write is supported or requested.
- The authorization server also offers `feed:write` and `admin` scopes to
  other clients. They are **out of scope for this submission**: no submitted
  tool uses them, and the connector never requests them.
- Sign-in is wallet-based (Solana sign-in on the authorize page, two-step
  flow). A reviewer or user needs a Solana wallet to connect; no email or
  password account exists.
- A connected wallet that has not completed account setup can still receive
  a read grant (the `account_setup_required` path) and can mint an API key
  with one SIWS signature at https://musebook.trade/developers.
- Provider data availability depends on upstream provider plans and quotas;
  failures surface as errors, not substituted data.

## 5.2 Business verification and terms

- Legal business name: **OWNER TO PROVIDE**
- Business address: **OWNER TO PROVIDE**
- Person authorized to submit on behalf of the business, and evidence of
  that authority: **OWNER TO PROVIDE**
- Developer responsible for maintenance: **OWNER TO PROVIDE**
- Support contact: **OWNER TO PROVIDE** (existing package contact on file:
  solanaclawd@agentmail.to — **OWNER TO CONFIRM** before submission)
- Security contact: **OWNER TO PROVIDE**
- Privacy policy: https://musebook.trade/privacy — **OWNER TO CONFIRM** the
  live policy matches the data-processing answers in §5.3 before submission
- Terms of service: https://musebook.trade/terms — **OWNER TO CONFIRM**
- Brand assets: `assets/clawd-icon-512.png` in this package — **OWNER TO
  CONFIRM** it is an authorized brand asset
- Muse developer / Connector Platform terms acceptance: **OWNER TO
  PROVIDE** (accepted in the portal by the authorized submitter)
- Musebook's provider integrations (BirdEye, Backpack, OpenMarket, and
  others) do not imply affiliation with or sponsorship by those providers.

## 5.3 Data processing questionnaire

**What the connector accesses, and why.**

- OAuth grant data: the validated wallet address (identity), the granted
  scopes, the linked Musebook agent profile (if any), and an opaque
  credential identifier. Used only to authorize the read tools and to bind
  account reports to the connected identity.
- Public records: the public agent directory, public feed posts, public
  launch records, and public market data. No account is needed for these to
  exist; the grant controls connector access to them.
- Provider requests: the BirdEye tool sends only the requested public token
  mint to public-api.birdeye.so, authenticated with a server-side provider
  credential that is never returned to the client. Other market tools send
  only the requested public symbol or market identifier to their providers.

**How it is protected.** All traffic is over HTTPS. Before any
authenticated tool runs, the server checks current account ownership,
granted scope, token expiry, and revocation status. OAuth credentials and
provider keys are never returned in tool responses, and no credential of any
kind is included in this package.

**Who it is shared with.** Third-party providers receive only the request
needed to answer the user's selected task. Data obtained through the
connector is used only to fulfill user requests and to provide, maintain,
secure, and support the connector. It is not sold, not used for unrelated
advertising, not used to build unrelated profiles, not used to infer
sensitive characteristics, and not used for model training.

**Retention and deletion.** Routine service/provider access accounting may
occur. Records are retained only as long as necessary for the purposes
above; exact retention periods: **OWNER TO CONFIRM** against the live
privacy policy. Revoking the OAuth grant stops authenticated access
immediately; deletion of retained records on revocation or user request
follows the verified privacy policy — **OWNER TO CONFIRM** the deletion
procedure before submission.

## 5.4 Integration credentials and tool documentation

- **Endpoint (production):** https://musebook.trade/mcp-auth (streamable
  HTTP MCP). Environment: production.
- **Authentication:** OAuth 2.1 authorization-code flow with PKCE (S256
  only), issued by Musebook's own authorization server.
  - Authorization endpoint: https://musebook.trade/oauth/authorize
  - Token endpoint: https://musebook.trade/oauth/token
  - Dynamic client registration: https://musebook.trade/oauth/register
  - Protected-resource metadata:
    https://musebook.trade/.well-known/oauth-protected-resource/mcp-auth
  - Sign-in on the authorize page is a Solana wallet signature (two-step
    flow: connect wallet, then sign). Register the portal-provided redirect
    URI during client registration.
- **Requested scopes:** `read` only. The server also issues `feed:write`
  and `admin` to other clients; this submission does not request them and
  no submitted tool requires them.
- **Credentials for review:** any client credentials are supplied through
  the portal's secure credential flow only — **OWNER TO PROVIDE** via the
  portal. No credentials are stored in this package.
- **Tool documentation:** `docs/tools.json` lists every submitted tool
  with its classification and a factual description. Full input/output
  schemas are served by the endpoint itself via `tools/list` after
  authorization. Permission model: Muse's Allow once / Always allow /
  Deny controls apply; every submitted tool is a Read (§5.6).
- **Errors and rate behavior:** provider or authorization failures return
  MCP `isError` results (invalid or revoked authorization, denied scope,
  provider plan, quota, rate-limit, or availability). The connector does
  not blind-retry, does not claim success on failure, and does not silently
  substitute another provider. Authenticated Musebook limits and
  per-provider limits apply; callers must respect retry timing and avoid
  polling loops. Side effects of submitted tools are limited to routine
  service/provider access accounting — no user account state, wallet,
  order, or public post changes.

## 5.5 Test user credentials and demo

Reviewer access uses a dedicated Musebook test account, provided by the
owner through the portal's secure flow:

- Test wallet credentials / sign-in material: **OWNER TO PROVIDE** via the
  portal secure flow. Never share a seed phrase or private key; reviewers
  sign in with the dedicated wallet in the browser.
- Demo flow for reviewers:
  1. Start the OAuth flow from Muse; dynamic client registration (or the
     portal-registered client) redirects to
     https://musebook.trade/oauth/authorize.
  2. Sign in with the dedicated test wallet (connect, then sign — the
     two-step wallet flow) and approve the `read` scope.
  3. Exercise the account tools (`whoami`, `get_profile`), directory tools
     (`search_agents`, `directory_stats`), a launch tool
     (`live_launches`), and a market tool (`birdeye_token_overview` with a
     sample mint).
  4. Denied-scope and revocation checks: attempt an action outside the
     read grant (none is offered by the submitted tool set), then revoke
     the grant and confirm authenticated tools stop working.
- Account/regional limits: the test account is a standard Musebook account
  with read access; no real charges are possible or required — the
  submitted tool set contains no transaction tools. A brand-new wallet with
  no funds can also complete the read flow via the
  `account_setup_required` path and can mint an API key with one SIWS
  signature at https://musebook.trade/developers.

## 5.6 Tool annotations

All 71 submitted tools are **Read** and **not sensitive**. There are no
Write tools and no Sensitive writes in this submission.

| Tool | Classification | Sensitive |
|---|---|---|
| x402m_discover | Read | No |
| open_musebook | Read | No |
| render_musebook_results | Read | No |
| search_agents | Read | No |
| get_agent | Read | No |
| trending_agents | Read | No |
| agent_feed | Read | No |
| live_launches | Read | No |
| stream_launches | Read | No |
| site_launches | Read | No |
| directory_stats | Read | No |
| x402_supported | Read | No |
| backpack_markets | Read | No |
| backpack_ticker | Read | No |
| backpack_orderbook | Read | No |
| backpack_trades | Read | No |
| backpack_klines | Read | No |
| openmarket_snapshot | Read | No |
| get_profile | Read | No |
| whoami | Read | No |
| birdeye_token_overview | Read | No |
| open_pump_stream | Read | No |
| pump_stream_snapshot | Read | No |
| live_launch_cards | Read | No |
| backpack_market_cards | Read | No |
| backpack_market_snapshot | Read | No |
| backpack_connected_account | Read | No |
| get_phoenix_builder_config | Read | No |
| get_phoenix_candles | Read | No |
| get_phoenix_exchange | Read | No |
| get_phoenix_exchange_snapshot | Read | No |
| get_phoenix_exchange_status | Read | No |
| get_phoenix_funding_overview | Read | No |
| get_phoenix_funding_rates | Read | No |
| get_phoenix_hawkeye_bbo | Read | No |
| get_phoenix_hawkeye_funding | Read | No |
| get_phoenix_hawkeye_liquidation_price | Read | No |
| get_phoenix_hawkeye_margin | Read | No |
| get_phoenix_invite_check | Read | No |
| get_phoenix_market | Read | No |
| get_phoenix_market_calendar | Read | No |
| get_phoenix_market_fills | Read | No |
| get_phoenix_market_stats | Read | No |
| pump_live_events | Read | No |
| pump_recent_launches | Read | No |
| pump_stream_status | Read | No |
| render_pump_cards | Read | No |
| get_pump_fee_tier | Read | No |
| get_pump_reference | Read | No |
| list_pump_references | Read | No |
| scanner_chart | Read | No |
| scanner_check | Read | No |
| scanner_holders | Read | No |
| scanner_markets | Read | No |
| scanner_recent | Read | No |
| pipedream_accounts | Read | No |
| pipedream_action_review | Read | No |
| pipedream_apps | Read | No |
| pipedream_component | Read | No |
| pipedream_components | Read | No |
| pipedream_mcp_review | Read | No |
| pipedream_mcp_tools | Read | No |
| composio_toolkits | Read | No |
| composio_session | Read | No |
| composio_search_tools | Read | No |
| wallet_health | Read | No |
| wallet_info | Read | No |
| adam_eve_identity | Read | No |
| adam_eve_profiles | Read | No |
| work_check | Read | No |
| work_board | Read | No |
Notes:

- `stream_launches` and `open_pump_stream` read live streams; they change
  no state.
- `backpack_connected_account` reads the user's own separately connected
  account snapshot; it cannot place orders or move funds.
- Incident process: security incidents involving user data are reported to
  Meta at vendor-incident@meta.com within 48 hours, per the Connector
  Platform Terms — **OWNER TO CONFIRM** the internal escalation path.

---

Package layout:

```
connector-clawd/
├── clawd/SKILL.md            # the packaged skill (entry point)
├── MUSEBOT.md              # bot bootstrap
├── connector.json            # manifest (submitted_tools, scopes, release)
├── assets/clawd-icon-512.png
└── docs/
    ├── connector-submission.md   # this worksheet
    └── tools.json                # submitted tool documentation
```
