# Muse connector release 3.15.2 (amended to 3.15.3 — see end)

Published October 18, 2026. Refresh of the 3.15.1 packages to current musebook.trade/mcp-auth facts, prepared against the current Muse Connector Platform guidelines. Verified live through musebook.trade DNS.

Downloads (all hashes verified live after deploy):

- https://musebook.trade/clawd-skills.tar.gz — 274 installable skills, 288 SKILL.md files, 3,469 archive entries, SHA-256 27cb41a83e2036856b892b5db0f44ae9d052859b3c7921904511ca59918feee7.
- https://musebook.trade/connectors/connector-clawd.tar.gz — version 3.15.2, 27 Read tool contracts, OAuth read scope, SHA-256 4f118856fe31faa482666e1bc511f42096c90f6a301dcaec30fdbfad20446bcc.
- https://musebook.trade/connectors/connector-birdeye.tar.gz — version 1.2.1, 1 Read tool contract, SHA-256 5b71a70d041e279791697ed8427fa4f5fb55dc37dcdcb429ea810b36467fb6b6.

What changed since 3.15.1:

- Skills archive rebuilt from the live library plus the current working skills: 44 skill directories updated (including the October 14 dynamic-credentials path repair), 2 added (anatomy, musebook-live-publish-verification). Nothing previously published was dropped.
- Hygiene fix: the previous live archive carried skills/cloudflare/config.json and a hardcoded account identifier in cf_worker_put.py. The config file is excluded and the staging copy now reads the account from the environment; the account-identifier canary scan is clean and no private-key blocks were found.
- Connector packages refreshed: the authenticated MCP now exposes 262 server tools; the submitted set is unchanged (the same 27 Read tools, all verified present in the reviewed read set). Submission documentation restructured to the guidelines' Section 5 worksheet; feed:write and admin scopes are documented as existing server-side but are NOT part of this submission, and money-movement / trade-order tools are excluded per guideline 4.6.
- Site worksheet at https://musebook.trade/connectors/submission.md updated to the same Section 5 content.

Known divergence: musebook.x402.life still serves the September 25 archive build (separate frozen deployment) — not changed by this release.

Still owner-side, unchanged from 3.15.1: business verification and brand authority, support/security contacts, privacy retention/deletion attestations, a dedicated reviewer account, and a real Muse OAuth callback exercise. The operator's stored Musebook OAuth grant currently returns 401 and needs a reconnect. No portal submission or approval is claimed by this release.

## Amendment — release 3.15.3 (October 18, 2026, owner-approved)

The submitted tool set was widened from the Oct-10 27 to the full reviewed
Read set: **71 tools**, all classified Read, none sensitive, all registered
on /mcp-auth under the read scope. The one reviewed tool held back is
`composio_execute_tool` — an execution gateway that classifies as a Write
under guideline 3.2 despite its server-side read-only policy. The 44 added
tools: 16 Phoenix market reads, 7 Pump data, 5 token scanner, 7 Pipedream
discovery/review, 3 Composio discovery, 2 wallet status, 2 Adam & Eve,
2 work-board reads. Full classification: the connector goal's
TOOL_INVENTORY.md (115 inventoried names: 101 Read / 9 Write / 5 Sensitive;
section 4.6 flags unchanged — request_backpack_order and request_agent_action
remain excluded).

Updated live hashes (verified after deploy):

- clawd-skills.tar.gz — SHA-256 7426c8bef011c9bbf0aedf6ba50e5be7a5d3fab57433deb0e5becb303e8b8281 (274 skills, 288 SKILL.md files, 3,469 entries).
- connector-clawd.tar.gz — version 3.15.3, SHA-256 fd6cc3341bc90beb8a608bd23877b7deeb1455fbe6ee6f4553135db6820fd9b5.
- connector-birdeye.tar.gz — unchanged (1.2.1, 5b71a70d...).
