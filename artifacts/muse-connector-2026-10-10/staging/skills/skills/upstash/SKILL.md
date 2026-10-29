# Upstash Box skill

Durable execution environments (isolated containers) for AI workloads: agent, shell, filesystem, git, snapshots, cron schedules, optional headless browser. Billed per active CPU time; auto-pause when idle unless `keepAlive`.

## Auth

- Connector `custom.upstash` (user-approved 2026-09-18), set up via Secure Vault card.
- Key is sent as `X-Box-Api-Key` header, only to `us-east-1.box.upstash.com`.
- Verified from the official `upstash-box` Python SDK source: default base URL `https://us-east-1.box.upstash.com`, header built by `build_headers()` as `{"X-Box-Api-Key": api_key}`.
- SSH also works: `ssh <box-id>@us-east-1.box.upstash.com` with the Box API key as the password.
- Transport rule: connector surrogate only substitutes on the Python urllib path — use `bin/box.py` (or the `dynamic_credentials` pattern); curl sends requests unauthenticated.

## CLI

`bin/box.py` (stdlib only, urllib + surrogate):

```
box.py list [--label X]
box.py status <box-id>
box.py exec <box-id> -- <shell command>
box.py logs <box-id> [--limit 50] [--offset 0]
box.py schedules <box-id>
box.py snapshots <box-id>
box.py snapshot <box-id> --name NAME
box.py create --runtime node|python|golang|ruby|rust[-alpine] [--name N] [--size small|medium|large] [--keep-alive] [--browser] [--labels a,b] [--env K=V ...]
box.py delete <box-id>      # irreversible
box.py pause <box-id>       # keep_alive boxes never idle-pause; pause() raises on them
box.py resume <box-id>
```

REST surface used (from SDK source): `GET/POST /v2/box`, `GET /v2/box/{id}/status`, `POST /v2/box/{id}/pause|resume`, `DELETE /v2/box/{id}`, `POST /v2/box/{id}/exec` with `{"command": ["sh","-c","..."]}`, `GET /v2/box/{id}/logs`, `GET /v2/box/{id}/schedules`, `GET/POST /v2/box/{id}/snapshots`.

## Boxes vs other "box" things in this workspace

- Upstash Boxes (this skill) are Upstash's product. As of 2026-09-18 there is one: `polite-bulldog-70639` ("clawdbot", node, small, keep_alive, idle, no schedules, no push loops).
- `~/workspace/clawd-box/` is a separate project: the agent server on a smol cloud machine. Its relay listener pushes launch events to the Cloudflare worker `/api/launches/ingest` every ~10s — that is what was burning the KV write quota, NOT an Upstash Box. Throttling that push is a change on the smol machine (or the worker), pending the user's throttle-vs-upgrade decision.
- Do not confuse the two when the user says "box".

## Notes

- Creating a box with an agent harness can incur LLM costs via Upstash-managed keys; confirm before creating agent boxes.
- `delete` is irreversible — snapshot first if the environment matters.
- API credentials authorize API access only, not wallet signing. Wallet policy unchanged.
