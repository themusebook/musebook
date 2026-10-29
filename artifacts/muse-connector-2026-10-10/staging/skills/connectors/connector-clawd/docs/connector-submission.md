# Clawd connector — Muse platform submission dossier

Everything below is ready to paste into the Muse connector submission form.
All fields were supplied by the user on 2026-09-19 — nothing is outstanding.

---

## Step 1 — Overview (form fields)

| Form field | Value to paste |
|---|---|
| **Connector name** | `Clawd` |
| **Company or developer** | `Musebook` — ⚠️ flag for user confirmation; alternative: the user's own dev handle/company name |
| **Product website** | `https://musebook.trade` |
| **Example prompts** | Paste the 7 prompts below, one per line/box as the form allows: |
| | 1. `Hey Clawd! Can you read https://musebook.trade/skill.md and get everything set up for me?` |
| | 2. `Help me connect my Solana wallet — I'd love to see my $CLAWD balance` |
| | 3. `What's launching on pump.fun right now? Show me the live stream` |
| | 4. `Can you walk me through onboarding to Phoenix perps?` |
| | 5. `I'd like to register my AI agent on-chain in the Musebook directory` |
| | 6. `Help me set up the DFlow trading stack, step by step` |
| | 7. `What else can you help me with? I'd love to see what you're capable of!` |
| **Connector icon** | `assets/clawd-icon-512.png` (512×512 PNG, lobster-claw mark, Solana purple `#9945FF` + green `#14F195` on dark, no text) |
| **Payments — does the connector accept payments?** | **No — "My connector does not accept payments"** (per live form selection) |
| **Your name** | `James Knox` |
| **Work email** | `solanaclawd@agentmail.to` |
| **Support email or URL** | `solanaclawd@agentmail.to` |
| **Privacy policy** | `https://musebook.trade/privacy` |
| **Terms of service** | `https://musebook.trade/terms` |
| **Anything else? (optional)** | Paste the blurb below: |

> Thanks for checking out Clawd! 🦞
>
> Clawd is a friendly Solana-native AI companion — part research buddy, part trading co-pilot, part on-chain citizen. This one connector bundles the whole world into a single install: 79 skills covering wallets, live market streams, pump.fun, Phoenix perps, DFlow, Jupiter, and an on-chain agent directory — all with browser-first signing, so your keys never leave your hands.
>
> There's also a Musebot version of me (Clawd himself!) running in the cloud if you'd like to chat with a live instance. Everything is open and community-driven — feedback, feature requests, and lobster puns are all welcome at solanaclawd@agentmail.to. Happy to answer any questions during review!

---

## Step 2 — Technical specs (form answers — verified live 2026-09-19)

Paste these into the form:

| Form field | Answer |
|---|---|
| **Connection type** | **Existing MCP** |
| **Hosted MCP endpoint** | `https://musebook.x402.life/mcp` |
| **API or MCP documentation** | `https://musebook.trade/skill.md` |
| **Access requirements** | None — the hosted MCP is public and read-only, no account, plan, region, or rate-limit requirements. Wallet actions and the 14 service connectors run entirely on the user's side (their own browser wallet + their own API keys), so nothing on the server needs credentials. |
| **Authentication methods** | Leave all checkboxes **unchecked** — no API keys, no OAuth, no auth of any kind on the hosted MCP |

Verified live 2026-09-19: POST initialize to `https://musebook.x402.life/mcp` returns 200 with `serverInfo: {name: "musebook", version: "1.0.0"}`. Streamable HTTP, stateless. Tools: `search_agents`, `get_agent`, `trending_agents`, `agent_feed`, `live_launches`, `stream_launches`, `directory_stats`, `x402_supported`. Resources: `musebook://skill.md`, `musebook://live-stream`.

Do NOT use the smolmachines VM URL (`https://clawd-connector-77509224ffaa.apps.smolmachines.com`) as the MCP endpoint — it is platform-auth-gated (401 without a smolmachines login). The Musebook MCP is the public one.

Notes for the form:
- **Skill entry point:** the single packaged skill `clawd` — file `clawd/SKILL.md`, version 3.9.1
  (byte-identical to `https://musebook.trade/skill.md` since the v3.9.1 sync).
  Two true install paths, both verified live 2026-09-19:
  - **Connector package (recommended):** `curl -fsSL https://musebook.trade/install-connector.sh | bash`
    downloads `https://musebook.trade/clawd-connector-v3.9.1.tar.gz` (clawd/SKILL.md,
    MUSEBOT.md, connector.json, docs/, assets/), verifies frontmatter
    (`name: clawd`, `version: 3.9.1`), installs `~/.muse/skills/clawd/SKILL.md` and a
    package reference copy at `~/.muse/clawd-connector/`. Fresh-shell test passed
    end-to-end from the live URL.
  - **Full 79-skill pack:** `curl -fsSL https://musebook.trade/install-clawd.sh | bash`
    downloads `https://musebook.trade/clawd-skills.tar.gz` (79 skill dirs, 289,142 bytes)
    into `~/.muse/skills/` and installs the same `clawd/SKILL.md`.
- **Manifest:** `connector.json` in this package (name `clawd`, slug `clawd`, version 3.9.1,
  homepage, skill entry, 14-connector list, install URLs, API base).
- **Bot bootstrap:** `MUSEBOT.md` — identity, six-law harness, CLAWD loop, wallet policy,
  trust ladder, memory rules; lets a fresh Muse bot instance load and BE Clawd.
- **Auth / data model:** the connector itself stores **no credentials**. All 14 connectors
  (Helius, DFlow, Imperial, Jupiter, Solana Tracker, BirdEye, OpenRouter, PayBox, Phoenix,
  wallet service, Pinata, Backpack, Composio, Nori) connect through the user's own secure
  flows (API-key cards, OAuth device flow, browser wallet signatures). Secrets live in the
  Secure Vault / connector store — never in files, prompts, or logs.
- **Public surfaces for verification (all checked live 2026-09-19):**
  - Skill doc: https://musebook.trade/skill.md (200, 58,121 bytes, text/markdown)
  - Connector installer: https://musebook.trade/install-connector.sh (200, 2,973 bytes, application/x-sh)
  - Release tarball: https://musebook.trade/clawd-connector-v3.9.1.tar.gz (200, 168,772 bytes, application/octet-stream; live bytes byte-identical to the packaged release)
  - Full-pack installer: https://musebook.trade/install-clawd.sh (200, 2,342 bytes)
  - 79-skill tarball: https://musebook.trade/clawd-skills.tar.gz (200, 289,142 bytes; 79 skill dirs verified)
  - Connectors page: https://musebook.trade/connectors.html (308 → https://musebook.trade/connectors → 200; normal Pages clean-URL normalization)
  - Privacy: https://musebook.trade/privacy (200) · Terms: https://musebook.trade/terms (200)
  - Read-only MCP (no auth): https://musebook.trade/mcp AND https://musebook.x402.life/mcp (both POST initialize → 200, `serverInfo: {name: "musebook", version: "1.0.0"}`)
  - Live relay: `wss://clawd-ws.fly.dev/ws` (base https://clawd-ws.fly.dev/ → 200)
  - API base: `https://musebook.trade/api/v1` (GET /api/v1/agents → 200)
  - Deployed machine (this submission's VM): `clawd-connector` mach-11a1efd489204dba900c562cd639b1d9 —
    `/healthz` → `{"status":"ok","skill":"clawd","version":"3.9.1","skills_installed":79}`;
    `/skills` → `count: 79`. Verified via authenticated `smol_cloud.py exec` (public URL is
    platform-auth-gated, 401 without smolmachines login — that is expected).
- **Wallet/security statement:** All transaction signing happens in the user's browser wallet
  (Phantom / Backpack). Local wallets exist only as named, single-venue, user-approved
  exceptions. The connector never asks for seed phrases or private keys. Jito-protected
  transactions are submitted only through Jito.
- **Pricing:** free to install; connectors bill through the user's own accounts
  (e.g. Helius/Jupiter/BirdEye API plans); machine usage is metered on smolmachines.

---

## Step 3 — Review (pre-submit checklist)

All items verified 2026-09-19. Evidence next to each item.

- [x] Connector name / company / website / prompts / icon prepared — values pasted into the live form by the user (name `James Knox`, work email + support `solanaclawd@agentmail.to`, privacy/terms URLs, payments = "does not accept payments", icon file attached). Note: the live Overview form shows **no separate category field** — the payments selection covers it.
- [x] User supplied name + work email + support contact — done in the form (see above).
- [x] `clawd/SKILL.md` opens cleanly and the install commands work from a fresh shell — ran `curl -fsSL https://musebook.trade/install-connector.sh | bash` with a clean HOME in /tmp: exit 0, installed `~/.muse/skills/clawd/SKILL.md` with frontmatter `name: clawd`, `version: 3.9.1`, plus `~/.muse/clawd-connector/` (MUSEBOT.md, connector.json, docs, assets). Test install cleaned up afterward.
- [x] `connector.json` validates (JSON parse) — parses OK; `install.command` = the real installer URL; `mcp.url` = `https://musebook.trade/mcp` (verified POST initialize → 200, musebook v1.0.0).
- [x] Icon renders at small sizes — `file` + PIL confirm genuine 512×512 RGB PNG; 32×32 downscale inspected: claw mark visible, high-contrast purple/green, slightly dark but readable.
- [x] `/healthz` and `/skills` on the deployed machine return healthy responses — machine `clawd-connector` (`mach-11a1efd489204dba900c562cd639b1d9`) is `started`; via `smol_cloud.py exec`: `/healthz` → `{"status":"ok","skill":"clawd","version":"3.9.1","skills_installed":79}`, `/skills` → `count: 79`.
- [x] No secrets in the package: grepped the package for `PRIVATE KEY`, `sk-`, `AKIA`, `hsurr:`, `mnemonic`, `seed phrase`, `api_key\s*[:=]`, `password\s*[:=]`, bearer tokens — every hit is negative policy language ("never print…"). No key material anywhere.

**Still genuinely manual for the user:** click **Next** on the Technical specs screen and submit; answer any review questions. Everything this package controls is done.

---

## Release history (connector package)

- v3.9.1 (2026-09-19) — initial connector release:
  - Pages deploys: `c56b0fa3-b995-4876-8427-21add66adbc7` (tarball + install-connector.sh), `75dc9abc-029e-44d6-ba36-f34fbc826c68` (rebuilt tarball with final connector.json install URLs)
  - `clawd/SKILL.md` synced byte-identical with `https://musebook.trade/skill.md` (one source of truth)

---

## Deployed instance (smolmachines)

- Machine: `clawd-connector` — `mach-11a1efd489204dba900c562cd639b1d9`
  (1 vCPU / 512 MB, `python:3.12-alpine`, port 8080, network open, no TTL/auto-stop —
  left running for the installable goal)
- URL: `https://clawd-connector-77509224ffaa.apps.smolmachines.com`
  ⚠️ currently returns **401 "smolmachines login required"** for unauthenticated visitors —
  platform-auth-gated by default. Reachable and verified through the authenticated
  `smol_cloud.py exec` path.
- On-disk: `/workspace/clawd-connector/` — `clawd/SKILL.md`, `MUSEBOT.md`,
  `connector.json`, `assets/clawd-icon-512.png`, `docs/`, plus `skills/` (all 79)
- Server: stdlib `server.py` on :8080 — routes `/`, `/healthz`, `/skills`,
  `/skill.md`, `/connector.json`. Started via `start.sh` (nohup, logs to `server.log`).
- Verified 2026-09-19: `/healthz` → `{"status":"ok","skill":"clawd",
  "version":"3.9.1","skills_installed":79}`; `/skills` → `count: 79`.
- Restart: `smol_cloud.py exec mach-11a1efd489204dba900c562cd639b1d9 --shell 'sh /workspace/clawd-connector/start.sh'`
- ⚠️ No key material was uploaded (no clawd-buyer/dflow-trader/phoenix-trader files —
  encrypted wallet files stay local-only, same rule as clawd-box).

---

## Package layout

```
~/workspace/connector-clawd/
├── clawd/SKILL.md          # the single packaged skill (entry point)
├── MUSEBOT.md              # bot bootstrap — load and BE Clawd
├── connector.json          # manifest
├── assets/clawd-icon-512.png
└── docs/connector-submission.md   # this file
```
