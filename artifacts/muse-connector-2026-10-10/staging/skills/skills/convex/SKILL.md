---
name: "convex"
description: "Use Convex when the user asks for Convex or this provider's API."
---

# Convex

## Purpose
Use Convex with the user-connected `custom.convex` credential.

## Tooling
Add service-specific CLIs under `~/workspace/skills/convex/bin/`.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and call `add_surrogate_to_request(...)`, `url_with_surrogate_query_param(...)`, or `url_with_surrogate_path_segment(...)` before authenticated requests, matching where the provider reads the key. If they use `urllib`, read JSON responses with `read_json_response(resp)` from the same helper instead of calling `resp.read()` directly. They must send only `hsurr:*` values, and only to the hosts below.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.convex`.

## Operating Rules
1. Use this skill when the user asks for Convex or this provider's API.
2. Restrict authenticated requests to: api.convex.dev, superb-parrot-112.convex.cloud (production since 2026-09-30; was accurate-condor-45), veracious-snake-356.convex.cloud (added 2026-09-18 — user supplied this deployment URL in chat).
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.

## Deploy blocker (proven 2026-09-19)
`npx convex deploy` CANNOT authenticate with the stored `custom.convex` surrogate, in any
process or language. Root cause, verified by direct API probes:
- The credential's placement is `{"custom_header": "Authorization"}`: the real key is
  injected only into the `Authorization` header, only for the exact process that fetched
  the surrogate. Child processes, node, and request bodies are never swapped.
- Convex's deploy2 protocol (`/api/deploy2/start_push`, `/wait_for_schema`, `/finish_push`)
  requires `adminKey` as a JSON **body** field and ignores the `Authorization` header
  (header-only auth returns 401 `MalformedAccessToken`; the body field is mandatory).
- No vault reconnect fixes this: no placement injects into a JSON body.
- The deploy-key exchange on `api.convex.dev` (`deployment/url_for_key`) also takes the
  key in the POST body. Same blocker.

Working path when the user supplies the deploy key transiently (precedent: 2026-09-17):
`bin/deploy_push_request.py` — node dumps the bundled push request locally via
`convex deploy --write-push-request` (no auth needed), then the script POSTs the three
deploy2 calls with the key (read via getpass, never stored) in header + body.
Do NOT re-investigate surrogate/header/body variants; they were all exhausted.

## Transport note (proven 2026-09-25)
`deploy_push_request.py`'s urllib POSTs die with `http.client.IncompleteRead(0 bytes
read)` on start_push in this VM — the egress proxy truncates large urllib responses
(same failure class as the DexScreener lesson in AGENTS.md). Fix: identical deploy2
protocol but with curl as the transport (brotli-compress the body in Python, pipe it
to `curl --data-binary @-` via stdin so the key never touches disk). Verified live:
start_push 200 -> schema complete -> finish_push 200 on prod deployment
accurate-condor-45. Also note: current convex CLI prints "Deployed Convex functions"
after `--write-push-request` but exits before any network call — the real push is the
deploy2 API sequence, not the CLI message.
