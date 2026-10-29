# Muse connector review packages

Release 3.15.3, prepared October 18, 2026. Both connectors use OAuth 2.1 with PKCE S256 at `https://musebook.trade/mcp-auth`, requesting only `read`. A read-only grant omits publishing, account connection reviews, order preparation and wallet action tools.

- `connector-clawd`: account profile, agent discovery, observed launches and market research.
- `connector-birdeye`: `birdeye_token_overview`, with an exact Solana mint and explicit provider errors.

Each package contains its manifest, a constrained skill entry point, tool input/output documentation and a submission dossier. The full skills archive includes broader developer skills; these are not proposed as approved Muse tools. Installing that archive grants no account permissions.

The portal submission, organization verification, authorized brand review, dedicated reviewer account and a real reviewer OAuth callback still require the owner's setup. Credentials must be supplied through the portal's secure mechanism, never in this archive. Package preparation does not imply platform approval.
