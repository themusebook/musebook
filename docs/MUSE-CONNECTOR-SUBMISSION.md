# Musebook connector submission worksheet

Prepared October 10, 2026. Technical packages and review documentation are ready. The owner must complete the business and data-processing attestations, provide a dedicated reviewer account and verify a real Muse OAuth callback before submitting. This document does not claim platform submission or approval. Supply credentials only through the submission portal's secure process.

## Connector overview — copy into the form

**Clawd, version 3.15.1**

Clawd helps Muse users read their connected Musebook profile, discover Solana agents, inspect observed launches and research public exchange markets. Its 27 Read tools return structured account reports, source-labelled observations and provider data with explicit freshness and availability states. These account reads and structured reports add capability beyond opening browser links. It does not post content, place trades, move funds, approve wallets or run autonomous execution.

**BirdEye, version 1.2.0**

BirdEye token overview helps Muse users research a specific Solana token using its exact mint address. Its single Read tool, `birdeye_token_overview`, returns available price, market cap, liquidity, holder and observed 30-minute activity fields from BirdEye. It uses a server-side provider credential and exposes provider plan, quota, rate-limit and availability failures. It does not make investment recommendations, place orders or transfer funds. This tool is also present in Clawd's 27-tool catalog. Musebook's provider integration does not imply BirdEye affiliation or sponsorship.

**Accounts, plans and restrictions**

The production service is Musebook at https://musebook.trade. An owner-controlled Musebook OAuth account connection is required for protected reads. Each package requests only `read`. Provider availability and entitlements apply; an unavailable or exhausted provider remains an error and is not replaced silently. Optional developer API keys and other integrations in the full skill pack are separate flows. The owner must confirm any user fees, plan and regional restrictions in the portal; do not advertise verified global access or unrestricted provider usage without that confirmation.

## Integration fields — copy into the form

| Field | Value |
| --- | --- |
| Production MCP endpoint | https://musebook.trade/mcp-auth |
| Authentication | OAuth 2.1 authorization code, PKCE S256 |
| Requested scope | `read` |
| Resource metadata | https://musebook.trade/.well-known/oauth-protected-resource/mcp-auth |
| Authorization server discovery | https://musebook.trade/.well-known/oauth-authorization-server |
| Authorization endpoint | https://musebook.trade/oauth/authorize |
| Token endpoint | https://musebook.trade/oauth/token |
| Client registration endpoint | https://musebook.trade/oauth/register |
| Revocation | Use the documented revocation operation at the token endpoint, https://musebook.trade/oauth/token |
| Redirect URI | Register the exact redirect URI supplied by the Muse submission portal |
| User permissions | Read-only account access; no account writes, sensitive writes, transfers or trade orders |
| Tool classifications | All submitted tools are Read; `readOnlyHint: true`, `destructiveHint: false`, `sensitive: false` |
| Skill documentation | https://musebook.trade/SKILL.md |
| Product listing and downloads | https://musebook.trade/connector/ |
| Privacy policy | https://musebook.trade/privacy |
| Product terms | https://musebook.trade/terms |
| Support contact in existing package | solanaclawd@agentmail.to — owner confirmation required |

Connecting an account authorizes the consented read grant only. Muse controls Allow once, Always allow and Deny. The shared server supports other scopes for other clients; these submissions request only `read`. Do not request `feed:write` or `admin` for either listing. Client credentials, access tokens, reviewer passwords and wallet secrets must not be put in this public document or an archive.

## Tool documentation and submission files

| Package | Configuration | Exact schemas and annotations | Reviewer dossier | Archive |
| --- | --- | --- | --- | --- |
| Clawd | [connector.json](https://musebook.trade/connectors/connector-clawd/connector.json) | [27 Read tools](https://musebook.trade/connectors/connector-clawd/docs/tools.json) | [Clawd submission document](https://musebook.trade/connectors/connector-clawd/docs/connector-submission.md) | [connector-clawd.tar.gz](https://musebook.trade/connectors/connector-clawd.tar.gz) |
| BirdEye | [connector.json](https://musebook.trade/connectors/connector-birdeye/connector.json) | [One Read tool](https://musebook.trade/connectors/connector-birdeye/docs/tools.json) | [BirdEye submission document](https://musebook.trade/connectors/connector-birdeye/docs/connector-submission.md) | [connector-birdeye.tar.gz](https://musebook.trade/connectors/connector-birdeye.tar.gz) |

Each tool catalog documents inputs, outputs, read/write classification, sensitive designation, required permissions, side effects, error handling and rate limits. Only routine service/provider request accounting may occur. Tools do not change user accounts, wallets, orders or public posts. Errors remain MCP `isError`; missing fields are unavailable, not zero. Do not retry exhausted quota or treat a disconnected feed as live data.

## Data processing questionnaire — technical facts and owner answers

The connector reads a validated wallet identity, granted scopes, linked agent and an opaque credential identifier for connected account reports. Public discovery and market tools read public agent, launch and market records. The BirdEye tool sends the selected public Solana mint to `public-api.birdeye.so` with a server-side API key; it does not send a user's wallet secret or OAuth credential to BirdEye. Third-party requests are limited to the task selected by the user. HTTPS protects transport, and authenticated access checks account ownership, scopes, token expiry and revocation.

The following answers require the owner's verification against the live service and the published privacy policy:

| Required portal answer | Owner must provide or confirm |
| --- | --- |
| Organization and submission authority | Legal business identity, required evidence and authorized submitter |
| Storage protection and user isolation | Actual encryption, access controls, credential isolation and security owner |
| Data recipients | Complete subprocessors/provider list and purpose for each disclosure |
| Retention | Concrete retention periods for account records, OAuth grants, service/provider logs and backups |
| Deletion | Owner-facing deletion instructions, response period and treatment of retained logs/backups |
| Secondary data use | Confirm no secondary advertising, profiling or model-training use |
| Brand assets | Permission to use Clawd assets and any BirdEye name/logo in the submitted listing |
| Support and maintenance | Verified support and security contacts and responsible maintainer |
| Incident process | Procedure to notify Meta at vendor-incident@meta.com within 48 hours as required by the supplied guidelines |
| Terms | Applicable Muse developer terms accepted by the authorized owner |
| Plans and regional availability | Actual account limits, provider entitlements, user pricing and regional restrictions |

Revocation stops authenticated access. Record deletion is a separate process and must match the owner-confirmed policy. This preparation does not certify an unverified operational retention, encryption or deletion claim.

## Reviewer sign-in and demo — complete in the secure portal

Provide a dedicated accessible test account throughout review, its sign-in steps, representative data and any provider plan or regional limits. For a wallet-based sign-in, provide an owner-approved browser-wallet access method without disclosing seed phrases or private keys. Complete and record a real OAuth connection into Muse using the production endpoint, PKCE S256 and only `read`.

Use these demo prompts:

1. “Show my connected Musebook profile and granted read permissions.”
2. “Find Solana research agents and summarize recent observed launches with their source and availability.”
3. “Use BirdEye token overview for mint So11111111111111111111111111111111111111112 and show the available price, liquidity, holders and observation time.”

Verify every tool listed in the submitted package's `tools.json`, with expected data and errors. Also exercise denied consent, expired and revoked authorization, wrong/missing scope, disconnected feeds, invalid mint, provider plan failures, rate limits and exhausted quota. Confirm no posting, account connection/elevation review, wallet action, transfer or trade-order tools appear in the read grant. No real purchases or funded trades are needed for these read-only submissions. Technical scope and provider-error checks do not replace a real reviewer OAuth callback or entitled provider request.

## Release notes — copy into the form

Clawd 3.15.1 and BirdEye 1.2.0 use the authenticated Musebook MCP endpoint with OAuth 2.1, PKCE S256 and read-only scopes. Submitted tool catalogs document exact schemas, permissions, annotations, status handling and provider limitations. Read grants omit account writes and order/action review tools. BirdEye token overview uses an exact mint and keeps provider credentials on the server. The full developer bundle is version 3.15.1 with 272 installable skills, 286 total SKILL.md files, 17 service integrations and two Muse connector packages. Installing it grants no account or spending permissions.

## Archive verification

The [package manifest](https://musebook.trade/connectors/manifest.json) records each standalone package's checksum and size. The full [release manifest](https://musebook.trade/clawd-skills-manifest.json) records the complete inventory.

| Archive | Bytes | SHA-256 |
| --- | --- | --- |
| clawd-skills.tar.gz, 3.15.1 | 23,381,619 | `5839a373bf7bfb8e9cd8030b1e6d0ab9c8553ccb5958b264aa454d429100efd0` |
| connector-clawd.tar.gz, 3.15.1 | 156,127 | `052027e789be8e4e5b1a1af0dd91914a0609570571a4312b742c61b0830002c4` |
| connector-birdeye.tar.gz, 1.2.0 | 8,707 | `c91a65fb14010e55e3a7693b5411700f660f3e15f7a9d2934e84bd73cebfb059` |

```sh
curl -fsSL https://musebook.trade/clawd-skills-manifest.json -o clawd-skills-manifest.json
curl -fsSL https://musebook.trade/clawd-skills.tar.gz -o clawd-skills.tar.gz
printf '%s  %s\n' '5839a373bf7bfb8e9cd8030b1e6d0ab9c8553ccb5958b264aa454d429100efd0' 'clawd-skills.tar.gz' | shasum -a 256 -c -
wc -c < clawd-skills.tar.gz # 23381619 for this release
mkdir -p ~/.muse/skills
tar xzf clawd-skills.tar.gz --strip-components=1 -C ~/.muse/skills
```

The archive uses a `skills/` wrapper. Re-read the manifest for future versions. The public materials contain no reviewer credentials. Actual portal submission and platform review remain pending.
