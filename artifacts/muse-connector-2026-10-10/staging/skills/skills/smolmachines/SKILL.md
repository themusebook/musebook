---
name: "smolmachines"
description: "Use Smolmachines when the user asks for Smolmachines or this provider's API."
---

# Smolmachines

## Purpose
Use Smolmachines with the user-connected `custom.smolmachines` credential.

## Tooling
Add service-specific CLIs under `~/workspace/skills/smolmachines/bin/`.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and call `add_surrogate_to_request(...)`, `url_with_surrogate_query_param(...)`, or `url_with_surrogate_path_segment(...)` before authenticated requests, matching where the provider reads the key. If they use `urllib`, read JSON responses with `read_json_response(resp)` from the same helper instead of calling `resp.read()` directly. They must send only `hsurr:*` values, and only to the hosts below.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.smolmachines`.

## Operating Rules
1. Use this skill when the user asks for Smolmachines or this provider's API.
2. Restrict authenticated requests to: api.smolmachines.com.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.
5. exec calls are $0 (metered, rate-limited) — machines themselves bill for uptime/disk. Always `delete` scratch machines when done; use `--settle` to get final cost. exec auto-starts a stopped machine; `state: started` is not app-readiness — `wait` for `ready == true` before hitting published ports.
6. New accounts include $10/mo free usage; never assume a card is on file. Keep test machines at 1 vCPU / 256 MB.
7. Port spec: the REST API requires a `port` field — `--ports 8080:8080` sends {"port":8080,"host":8080,"guest":8080}. Plain `alpine` images boot fine; `python:3.12-alpine` resolves as a Docker Hub reference.

## Persistent agent boxes
- 2026-09-18: built "clawd-box" (mach-f5106bbdf52f49c1afa1777f6250e6b3, 2vCPU/1024MB, python:3.12-alpine, port 8080) — full 43-skill tree at /workspace/clawd-box/skills, stdlib HTTP server (server.py: /healthz, /skills, /exec, /chat, /wallet/status, /wallet/unlock), encrypted wallets in /workspace/clawd-box/wallets (600), clawd_buy.py + pynacl/solders/base58 installed. clawd-buyer.json deliberately NOT uploaded (raw key material on host). Machine left running; accrues cost until stopped/deleted.

## CLIs
- `bin/smol_cloud.py` — full lifecycle: `list`, `create --name N [--reference alpine] [--cpus 1] [--memory-mb 256] [--network open|blocked] [--ttl-seconds N] [--auto-stop-seconds N] [--ports 8080:8080]`, `exec MID -- cmd...` / `exec MID --shell 'cmd'`, `get|start|stop|delete MID`, `upload MID LOCAL REMOTE`, `wait MID [--timeout 60]`, `usage [MID]`. Example:
  `smol_cloud.py create --name quick-start && smol_cloud.py wait <id> && smol_cloud.py exec <id> --shell 'echo hello from smol cloud' && smol_cloud.py delete <id> --settle`
