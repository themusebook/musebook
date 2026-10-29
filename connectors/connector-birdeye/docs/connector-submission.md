# BirdEye — Muse Connector Platform submission worksheet (brief)

Release 1.2.1 — prepared October 18, 2026. Structured to match §5 of the
Muse Connector Platform guidelines. Owner-supplied fields are marked
**OWNER TO PROVIDE** / **OWNER TO CONFIRM**.

- Connector name: `BirdEye`
- Hosted MCP endpoint (production): https://musebook.trade/mcp-auth
- Submitted tool: `birdeye_token_overview` (single tool, Read)

## 5.1 Connector overview

**Intended users.** Muse users who want exact-mint Solana token overview
data from BirdEye — price, market cap, liquidity, holders, and observed
30-minute activity — inside Muse, without a separate BirdEye account.

**Supported tasks.** One read-only tool: `birdeye_token_overview`
(documented in `docs/tools.json`). Example prompt: "Show wrapped SOL price,
market cap, liquidity, holders and observed 30-minute activity using mint
So11111111111111111111111111111111111111112."

**Value beyond the browser.** The tool completes the information task in
Muse with structured provider data, source attribution, and a retrieval
timestamp; provider plan or quota failures return explicit errors instead
of partial or substituted data.

**Restrictions.** Read-only: scope `read` only; no trades, transfers,
signing, or posting. Data is research information, not financial advice.
The tool is one of the 262 tools on the shared Musebook MCP server; this
submission covers only this tool. Musebook's integration does not imply
BirdEye affiliation or sponsorship.

## 5.2 Business verification and terms

- Legal business name: **OWNER TO PROVIDE**
- Business address: **OWNER TO PROVIDE**
- Authorized submitter + evidence of authority: **OWNER TO PROVIDE**
- Maintenance developer, support contact, security contact: **OWNER TO
  PROVIDE** (existing package contact on file: solanaclawd@agentmail.to —
  **OWNER TO CONFIRM**)
- Privacy policy: https://musebook.trade/privacy — **OWNER TO CONFIRM**
- Terms of service: https://musebook.trade/terms — **OWNER TO CONFIRM**
- Brand assets: **OWNER TO CONFIRM** authorization to use the BirdEye name
  for this provider integration listing
- Muse developer / Connector Platform terms acceptance: **OWNER TO
  PROVIDE** (in the portal)

## 5.3 Data processing questionnaire

The tool sends only the requested public token mint to
public-api.birdeye.so, authenticated with a server-side provider credential
that is never returned to the client. The OAuth grant identifies the
connected wallet for access control only. Transport is HTTPS; scope,
expiry, and revocation are checked before the tool runs. No data is sold,
used for unrelated advertising or profiling, or used for model training.
Revoking the grant stops access; retention and deletion of routine access
accounting follow the verified privacy policy — **OWNER TO CONFIRM** exact
retention and deletion procedures. A separate optional direct API-key flow
(`custom.birdeye`, the user's own BirdEye key in the Secure Vault) exists
outside this submission and is not connected or stored by Musebook OAuth.

## 5.4 Integration credentials and tool documentation

- Endpoint (production): https://musebook.trade/mcp-auth
- Auth: OAuth 2.1 authorization-code + PKCE S256 via Musebook's
  authorization server — authorize:
  https://musebook.trade/oauth/authorize; token:
  https://musebook.trade/oauth/token; dynamic client registration:
  https://musebook.trade/oauth/register; resource metadata:
  https://musebook.trade/.well-known/oauth-protected-resource/mcp-auth.
  Sign-in is a Solana wallet signature on the authorize page (two-step
  flow).
- Requested scopes: `read` only.
- Credentials: supplied through the portal's secure flow only — **OWNER
  TO PROVIDE** via the portal. No credentials are in this package.
- Tool documentation: `docs/tools.json`; full schemas are served by the
  endpoint via `tools/list` after authorization.
- Errors/rate behavior: provider plan, quota, and rate-limit failures
  return MCP `isError`; no blind retries and no silent provider
  substitution. Pace calls (~1.2s apart) with backoff on 429.

## 5.5 Test user credentials and demo

- Dedicated Musebook test account credentials: **OWNER TO PROVIDE** via
  the portal secure flow (never a seed phrase or private key).
- Demo: connect with PKCE S256 and scope `read`, sign in with the test
  wallet, call `birdeye_token_overview` for a sample mint, then revoke the
  grant and confirm the tool stops working. No real charges are possible —
  the submitted set has no transaction tools.

## 5.6 Tool annotations

| Tool | Classification | Sensitive |
|---|---|---|
| birdeye_token_overview | Read | No |

No Write or Sensitive tools are submitted. Incident process: security
incidents involving user data are reported to Meta at
vendor-incident@meta.com within 48 hours, per the Connector Platform Terms
— **OWNER TO CONFIRM** the internal escalation path.
