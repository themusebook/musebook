---
name: "e2b"
description: "Use E2B when the user asks for E2B or this provider's API."
---

# E2B

## Purpose
Use E2B with the user-connected `custom.e2b` credential.

## Tooling
Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py`
and call `add_surrogate_to_request(...)`, `url_with_surrogate_query_param(...)`,
or `url_with_surrogate_path_segment(...)` before authenticated requests, matching
where the provider reads the key. The E2B control plane is `api.e2b.app` and the
Node SDK sends the key in the `X-API-KEY` header — so for SDK-based flows, fetch
the surrogate via `dynamic_credential_entry("custom.e2b")` and hand it to the SDK
as the API key; Sentinel swaps the `hsurr:*` value for the real key on approved
egress. They must send only `hsurr:*` values, and only to the hosts below.

## Auth
The credential is already stored; nothing here collects one. Never ask the user
to paste a raw key in chat, set a secret environment variable, pass a secret
flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the
key. Check that the credential was attached at all: a request built without the
helpers named under Tooling carries nothing, and that looks exactly like a
wrong or under-scoped token. Only once a request that did carry the credential
is still rejected, call `credentials.request_api_access` with `reconnect` to
replace it. The connector is stored as `custom.e2b`.

## Operating Rules
1. Use this skill when the user asks for E2B or this provider's API.
2. Restrict authenticated requests to: api.e2b.app.
3. Do not print, log, or persist raw credentials. Surrogate values may appear
   in memory only for the duration of the request that carries them.
4. Sandbox lifetime is tier-capped: this team is Base tier, so 1h is the max
   sandbox timeout (the API rejects larger with 400). Data inside a sandbox is
   ephemeral.
5. Sandbox public URL format is port-prefixed: `https://<port>-<sandboxId>.e2b.app`
   (via `sandbox.getHost(port)`).

## CLIs
- `bin/e2b_deploy.py` — deploy the AgentWallet vault server to a fresh E2B
  sandbox: `e2b_deploy.py [--timeout 3600]`. Generates a fresh 64-hex
  VAULT_PASSPHRASE + VAULT_API_TOKEN per deploy (token printed once for the
  user), starts the server on port 9099, probes /api/health (200 with token,
  401 without), and prints the sandbox ID + public URL. Long-running: run in
  background.
