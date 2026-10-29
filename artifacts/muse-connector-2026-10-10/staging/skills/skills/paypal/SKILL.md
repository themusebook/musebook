---
name: "paypal"
description: "Call the PayPal REST API: OAuth token exchange plus arbitrary endpoint calls on live or sandbox."
---

# PayPal

Call PayPal's REST API. Auth is OAuth 2.0 client-credentials: the REST app's
client ID + secret are exchanged for a short-lived Bearer token.

## Why there is no stored connector

PayPal needs **two** secrets per request (client ID + client secret) and the
vault connector holds exactly one, so `custom.paypal` was declined. This skill
reads the pair at runtime and never stores, prints, or logs them.

## Credentials (user-managed)

In order of precedence:

1. Env vars: `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET`
2. File `~/.config/paypal/credentials` (mode 0600):
   ```
   PAYPAL_CLIENT_ID=...
   PAYPAL_CLIENT_SECRET=...
   ```

The agent never writes this file and never reads the values into chat. The
Bearer token cache at `~/.cache/paypal/token_<env>.json` (0600) holds only the
short-lived token, refreshed automatically (one retry on 401).

## CLI

`bin/paypal.py` (stdlib only):

- `paypal.py token [--env live|sandbox] [--force]` — exchange credentials,
  print metadata only (app_id, scope, seconds until expiry). Use this to verify
  a credential pair; a 200 with an `app_id` means the pair works.
- `paypal.py call [--env live|sandbox] METHOD /v2/path [--data '{...}']` —
  call any REST endpoint with the Bearer token.

Hosts: live `api-m.paypal.com`, sandbox `api-m.sandbox.paypal.com`
(default `--env live`, per the user's choice).

## Rules

- Live = real money. Read-only calls are free to run; anything that moves
  money (payouts, captures, refunds, invoices sent) needs the user's explicit
  approval of the exact terms first, per the standing money-move policy.
- Sandbox and live REST apps have **different** credential pairs; do not mix
  them across `--env`.
- Never print the client secret or the raw access token. `token` reports
  metadata only; keep it that way.
