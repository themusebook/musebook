# Musebook release package and source alignment — 2026-10-10

The frozen frontend inputs match the user-designated `musebook-private/web-react` exactly. Source SHA-256: `d1318baa00c5cac53a5110b27a75f1bf8221c361dbcfbceb2ea610d80699f716`. Built artifact SHA-256: `5c85aaa1fa55bd9ff038442e586831cbff825fd68ef64ff62e799b570bd609e6`. Entry: `/assets/index-BazqlYN_.js`. Build time: `2026-10-10T19:29:44.179Z`.

Private base revision: `a6879417018e3763550d32b21bc1e782c0dd4548`. The release includes reviewed uncommitted changes; this revision is a history anchor, not a claim that the deployed inputs form a clean committed checkout. The source hash identifies the complete reviewed inputs. Public integration repository base: `4a3540d049999107cc598cbd0feb63555a9beb5c`.

This report covers source and package alignment. Promotion, normal-domain routing and live user-flow evidence are recorded separately. No private environment values, credentials, machine-specific absolute paths or runtime source are included.

## Final downloadable archives

| Archive | Version | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `musebook-1.2.0.tgz` | 1.2.0 | 132,536 | `65ade79affb5daca9b9daaacc567ff714666e2f1555b8132639fe934af3c4bf5` |
| `musebook-sdk-1.5.0.tgz` | 1.5.0 | 45,119 | `10aa06c688680cdcf2aba4a475c390829f7c001c440a5cf68f5a5e67ef7f782f` |
| `musebook-tui-0.1.2.tgz` | 0.1.2 | 25,847 | `05b6b0afab4b118de1b96bfe9c60aae5202e18e78ebd143b311d3dff11fdce7e` |
| `connector-clawd.tar.gz` | 3.15.1 | 156,127 | `052027e789be8e4e5b1a1af0dd91914a0609570571a4312b742c61b0830002c4` |
| `connector-birdeye.tar.gz` | 1.2.0 | 8,707 | `c91a65fb14010e55e3a7693b5411700f660f3e15f7a9d2934e84bd73cebfb059` |
| `clawd-skills.tar.gz` | 3.15.1 | 23,381,619 | `5839a373bf7bfb8e9cd8030b1e6d0ab9c8553ccb5958b264aa454d429100efd0` |
| `musebook-plugin.zip` | 1.1.5 | 1,008,808 | `e90ca181c16e13f2e9980c1b8bbd60282d8f51ec77d568ea4f3fc706956835a5` |
| `clawd-plugin.zip` | 3.15.1 | 26,160,278 | `2491b0ba6904aed552cc5da612865d14ab457154fbf2ded6a550620ace0e46fc` |
| `clawd-research-plugin.zip` | 1.2.1 | 1,013,116 | `68fef7e925c96167abddc68c59f0ee09d8b4273bcd0d2de6fd4ae4ee756454f0` |

## Counts and provenance

The original Clawd 3.15.1 tar contains **272 installable skills**, **286 SKILL.md documents**, including **14 nested documents**, and **2,626 regular files** across **3,306 entries**. There are **17 service connectors** and **two connector packages**. Nested guides are not extra installable skills.

The full plugin adds one Musebook workflow: **273 workflows total**, **272 discoverable** and **one manual-only** (`review-animations`). Of the 272 original source skills, 271 remain discoverable and one remains manual; the added overlay accounts for the 272nd discoverable plugin workflow. `SOURCE.json` verifies all 2,626 original files exactly. Twenty-four frontmatter normalizations retain their exact originals and record both original and packaged checksums.

The public MCP contract snapshot contains **23 tools**. Research retains **14 tools**, one skill and one no-auth connection; its exact output schemas and safety hints match the verified live catalog. Full developer editions retain one `/mcp-auth` OAuth connection and record 23 public output contracts plus four account contracts. Schema records do not grant scopes or imply every account tool is available to a read-only credential. No connections or grants were added.

## Source comparisons

- CLI: all **33** packed files match the current public GitHub allowlist.
- SDK: all **32** packed files match current GitHub SDK source and compiled distribution.
- Connector packages: all **9 Clawd** and **7 BirdEye** regular files match extracted GitHub sources; the archive bytes also match.
- Musebook and Research plugins: all **11** files in each ZIP match extracted source copies in GitHub and the designated frontend. Full Clawd provenance covers every original source file.
- TUI: preserved the existing compiled 25-file release. Package metadata, README and config match GitHub, and the evaluated compiled system-prompt string exactly matches current TypeScript source. This report does not claim every compiled TUI module was rebuilt from current source; the older private TUI checkout was not used to overwrite this release.
- Canonical skill, installer, OpenAPI, llms index, current guide and v0.6 paper artifacts match their GitHub mirrors exactly. Clawd manifest JSON is semantically identical despite formatting differences. All published archive sizes and SHA-256 values were rechecked.

## Production availability and validation

OpenAPI retains all **237 paths**, with these seven path items and operations explicitly marked `x-musebook-deployment-status: source_only` and described as lacking a production handler:

- `/api/metaplex/identities`
- `/api/metaplex/identities/{hash}/{file}`
- `/api/metaplex/i/{key}/{file}`
- `/api/metaplex/identities/verify`
- `/api/otc/meteora/launch`
- `/api/otc/coins`
- `/api/otc/ipfs`

The full research generation pipeline completed after correcting the active SDK version, the fourteen-tool Research authority row and the inaccurate no-UI claim. Research source hash: `207d825f6d3741a0fc66dbbfffc3d98b48f295b750cabb1d95010c5236bdc80a`. PDF SHA-256: `5585f3412f2c2e84c5d8a3a8d900bb177cc8995847b3ca12ae1db84ffe8b8465`. The current guide, MD, HTML, PDF and research manifest are synchronized; historical paper files remain intact. These generated artifacts are not embedded in any reviewed plugin ZIP, so their regeneration does not change plugin ZIP provenance.

The complete frontend suite passes **525/525** checks, the focused documentation, catalog and research suite passes **25/25**, and package tests pass **3/3**. The Vercel static output matches all **1,097** built distribution files byte-for-byte. Release source/artifact hashes and exact original-source parity were recomputed. The curated GitHub diff passes whitespace checks. Active README versions, tool/connector counts, SDK version, directory count wording and the frontend CLI source link were corrected. No remaining package or documentation alignment concern was found in this bounded review. Live release verification belongs to the coordinator's release evidence. The fresh comparison rechecks all nine archives and 2,729 packaged source files; it also verifies the preserved TUI metadata and evaluates the compiled system prompt against current TypeScript source.

The largest plugin ZIP is 26,160,278 bytes, below the 26,214,400-byte Pages limit by 54,122 bytes. No wallet execution, paid operation, owner OAuth callback, OpenAI approval or production availability of source-only handlers is claimed.

Detailed machine-readable evidence: [package-source-alignment.json](package-source-alignment.json).


## Browser evidence and release carryforward

The original browser report remains unchanged: `2026-10-10T19:10:07.235Z` through `2026-10-10T19:11:02.805Z`, source `a88c5ca641fe65d003d649e97d27eede144d66ace06d142a597e64b6dc47b391`, artifact `1d93ad66fa5a5758a86500a298c45f5cdc4983f9c4e376003ccf9a821b93eff2`. Its actual screenshot times, release hashes and then-current CLI digest are preserved. It is not represented as a fresh browser run on the final release.

The first 1,097-file comparison changed only `_redirects` and `release.json` for the route correction (`88a7c82f7f4ed97c3632c50627e4943133bd1b19a906b742707ee8ef6246b2eb` / `2e41768e88acbee0d5148dbb2f6f45c417e62c4cc4fd0c9dd70e0bd5948c15c6`). The final documentation correction changed exactly seven files: `agentic-layer.md`, `clawd-agentic-layer-whitepaper.pdf`, `downloads/manifest.json`, `downloads/musebook-1.2.0.tgz`, `release.json`, `research/clawd-agentic-layer-v0.6.pdf` and `research/manifest.json`. No files were added or removed. Compiled HTML/JavaScript/CSS, the paper Markdown/HTML and the other eight archives remain byte-identical.

Rendering, copy controls, clipboard-denial fallback, mobile navigation and unchanged connector/skill downloads are carried forward on that byte comparison. The old CLI/PDF/release hashes and previously corrected route checks are excluded from carryforward. Fresh package comparisons establish the final CLI/PDF bytes; current normal-domain route and runtime checks are reported separately. `package-source-comparison.json` includes every changed file's old and final SHA-256. Both original byte inventories are included.

The final frontend suite passes 525/525 on the final inputs, and both the frozen and designated-original release checks pass. `build-revision-attestation.json` records the metadata-only correction of the isolated build's `unknown` revision to the verified private base revision; source and artifact hashes are unchanged by that correction.

## Strict HTML transformation evidence

`html-transform-review/transform-review.json` preserves four reviewed HTML comparisons and their actual live-check time, `2026-10-10T19:20:11.896507+00:00`. These HTML bytes are unchanged in the final artifact. Pinned same-origin WebMCP additions, the exact preserved navigation shim, restricted Cloudflare challenge data and reversible terminal email obfuscation normalize to the exact frozen documents. All fifteen mutation checks reject unknown changes. The bridge injector is absent from the captured Musebook Worker and is not independently attributed. The copied GET/HEAD verifier retains its reviewed checksums; no private Worker module or credentials are included. Normalization cannot waive real routing failures.
