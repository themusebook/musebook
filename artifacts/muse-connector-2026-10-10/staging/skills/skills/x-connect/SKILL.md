---
name: "x_connect"
description: "Post tweets with media via X API v2 using the stored custom.x OAuth2 credential"
---

# X

## Purpose
Use X with the user-connected `custom.x` credential.

## Tooling
- `bin/tweet.py` — post the pump.fun top-10 pulse as a tweet with generated art.
  `tweet.py --pulse-json digest.json --image art.png [--dry-run]`
  Uploads the image via `POST api.x.com/2/media/upload` (JSON base64, `media_category: tweet_image`),
  then posts via `POST api.x.com/2/tweets` with `media.media_ids`. Composes text ≤280 chars.
  **X allows only one cashtag per post**: token symbols are listed WITHOUT `$`; `powered by $CLAWD`
  is the single cashtag. Exits 0 with "no qualifying launches" when the digest is empty.
  Verify it with a read-only probe (`GET /2/users/me`) if a post fails.

Add further service-specific CLIs under `~/workspace/skills/x-connect/bin/`.

CLIs must use authd or shared connector helpers for authenticated requests. They must not read OAuth client credentials, browser callback payloads, refresh tokens, access tokens, or Muse auth files directly.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.x`.

## Operating Rules
1. Use this skill when the user asks for X or this provider's API.
2. Restrict authenticated requests to: api.x.com, api.twitter.com.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.
