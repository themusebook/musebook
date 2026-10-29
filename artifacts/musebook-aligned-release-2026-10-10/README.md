# Musebook production alignment — 2026-10-10

The designated private frontend, canonical website, terminal Pages deployment and GitHub package/documentation mirrors now share the reviewed release. Stale plugin versions, tool counts, archive metadata, CLI documentation and research provenance were synchronized. The uppercase skill URL and whitepaper PDF route were repaired.

- Canonical: https://musebook.trade
- Terminal: https://terminal.musebook.trade
- Vercel deployment: `dpl_Hwc1U91VRNw2EaQKmNmn1tKNk5Vb`
- Pages deployment: https://1d01c558.musebook-3al.pages.dev
- Worker version: `36310a5c-b5a5-4395-8282-72577857502a`
- Source SHA-256: `d1318baa00c5cac53a5110b27a75f1bf8221c361dbcfbceb2ea610d80699f716`
- Artifact SHA-256: `5c85aaa1fa55bd9ff038442e586831cbff825fd68ef64ff62e799b570bd609e6`

The private base revision is `a6879417018e3763550d32b21bc1e782c0dd4548`. Reviewed uncommitted changes are included; the source hash identifies those complete frozen inputs. GitHub mirrors the CLI, SDK, skills, connectors, plugin packages and public documentation rather than containing the complete private application tree.

Validation passed: **525 frontend tests**, **1,068 normal-DNS GET/HEAD checks** across canonical/Vercel/terminal/Pages, **12 final route and download checks**, **97 Cloudflare boundary tests**, and **9 archive / 2,729 packaged-file comparisons**. The earlier 20-route desktop/mobile browser report preserves its original timestamps and release hashes. Final byte comparison proves every compiled HTML/JS/CSS file and all 274 assets unchanged; new CLI/PDF bytes were verified independently.

The Worker runtime was preserved byte for byte while publishing the reviewed OpenAPI documentation, static assets, frontend pins and exact historical missing runtime bindings. The final publication preserves all previous binding descriptors except the four explicit frontend URLs, all 83 secret descriptors, six named handlers, runtime metadata and cron schedule. The historical agent feed limiter was restored without creating a resource.

Town and Convex-backed directory reads remain unavailable because Convex disabled the deployment after free-plan limits were exceeded. The on-chain agent feed still returns `503 agent_indexer_unavailable` after limiter restoration; its remaining cause is unverified. Seven additional Metaplex/OTC API contracts are marked `source_only` in the public OpenAPI and frontend docs because their handlers are absent from the preserved production runtime. Full backend smoke remains failed at Town state; public MCP catalogs contain 23 and 14 tools, which does not prove every provider-backed tool succeeds.

Use [release context](release-context.json), [validation summary](validation-summary.json), [live parity](live-parity.json), [package comparisons](package-source-alignment.md), [final browser checks](live-browser/final-route-release-check.json), [Worker proof](runtime/FINAL-worker-publication.json), and [backend diagnosis](runtime-evidence/api-availability.json) to inspect the evidence. Reports contain no credential values, raw Worker modules/settings, cookies or downloaded archives.
