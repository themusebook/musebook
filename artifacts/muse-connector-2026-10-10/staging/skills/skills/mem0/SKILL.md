---
name: "mem0"
description: "Use Mem0 when the user asks for Mem0 or this provider's API."
---

# Mem0

## Purpose
Use Mem0 with the user-connected `custom.mem0` credential.

## Tooling
- `bin/mem0.py` — persistent memory CLI through the `custom.mem0` connector
  (surrogate auth, raw key never visible). mem0 auth header is
  `Authorization: Token <key>` (mem0 canonical; `Bearer` is rejected).
  ```
  mem0.py search <user_id> <query> [--top-k 5]
  mem0.py add <user_id> "<user message>" ["<assistant message>"] [--meta k=v ...]
  mem0.py get <user_id> [--limit 20]      # list memories for a user
  mem0.py delete <user_id> <memory_id>     # delete one memory
  mem0.py clear <user_id>                 # delete ALL memories for a user
  mem0.py ping                            # verify the stored credential works
  ```
- API quirks (verified 2026-09-20): `POST /v1/memories/search/` wants
  `user_id` TOP-LEVEL (nested `filters.user_id` 400s); search returns a bare
  array, not `{results:[...]}`; adds are async (PENDING) — a fresh add takes
  seconds to become searchable, so read-after-write tests must wait/retry.

## Auth

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.mem0`.

## Operating Rules
1. Use this skill when the user asks for Mem0 or this provider's API.
2. Restrict authenticated requests to: api.mem0.ai.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.
