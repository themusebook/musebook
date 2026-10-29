---
name: "pinata"
description: "Use Pinata when the user asks for Pinata or this provider's API."
---

# Pinata

## Purpose
Use Pinata with the user-connected `custom.pinata` credential.

## Tooling
Add service-specific CLIs under `~/workspace/skills/pinata/bin/`.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and call `add_surrogate_to_request(...)`, `url_with_surrogate_query_param(...)`, or `url_with_surrogate_path_segment(...)` before authenticated requests, matching where the provider reads the key. If they use `urllib`, read JSON responses with `read_json_response(resp)` from the same helper instead of calling `resp.read()` directly. They must send only `hsurr:*` values, and only to the hosts below.

## Auth
Two credential paths, tried in order by `bin/pinata_pin.py`:

1. The stored `custom.pinata` connector surrogate (Bearer on
   `api.pinata.cloud`).
2. The `PINATA_JWT` environment variable (user-supplied JWT, transient —
   never written to disk, never printed).

Note (2026-09-18): the stored connector currently holds the Pinata *API key*
rather than the JWT, so surrogate auth 401s with "token is malformed". The CLI
automatically retries with `PINATA_JWT` on 401/403. If the user re-enters the
JWT via `credentials.request_api_access` with `reconnect`, path 1 works again.

## Operating Rules
1. Use this skill when the user asks for Pinata or this provider's API.
2. Restrict authenticated requests to: api.pinata.cloud.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.
