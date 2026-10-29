# Muse connector release 3.15.1

Published October 10, 2026. The canonical archive, static manifest, /api/bundle, skill API and both standalone connector downloads were verified through normal musebook.trade DNS. Exact evidence is in verification.json.

Downloads:

- https://musebook.trade/clawd-skills.tar.gz — 272 installable skills, 286 SKILL.md files, both connector packages.
- https://musebook.trade/connectors/connector-clawd.tar.gz — 27 Read tool contracts, OAuth read scope.
- https://musebook.trade/connectors/connector-birdeye.tar.gz — 1 Read tool contract, OAuth read scope.

The stale file came from Cloudflare's pinned older Vercel release. Vercel already served the updated file. A dedicated MUSEBOOK_BUNDLE_UPSTREAM now pins only these downloads and their manifests; the current app and payment origins retain their existing settings. The Worker patch preserved 119 existing bindings and static assets. Source changes were pushed to both repositories.

The app build, focused server/routing checks, catalog checks, public CLI tests, exact patched Worker tool SDK checks and deterministic archive rebuild passed. Private key block and recognized provider credential scans found no matches in the archive. OAuth discovery and unauthenticated denial were verified live. A real Muse login callback, successful production BirdEye provider entitlement and dedicated reviewer account were not exercised. Business authority, authorized brand assets and operational privacy/retention/deletion answers still require owner confirmation in the portal.

GitHub currently reports Solizardking/musebook as private, despite the supplied handoff calling it public. Repository visibility was preserved. The live tarballs are publicly downloadable.
