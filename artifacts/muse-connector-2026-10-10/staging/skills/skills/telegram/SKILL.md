---
name: "telegram"
description: "Call the Telegram Bot API with the user's stored credential (surrogate-authenticated, token never read). Verify the bot, send messages, read updates."
version: 1.0.0
---

# Telegram

## Purpose
Call the Telegram Bot API with the user-connected `custom.telegram` credential.

## Tooling
`bin/tg_api.py METHOD [payload.json|-]` — surrogate-authenticated Bot API caller.
Reads payload from a JSON file arg or stdin. Prints response JSON.

Examples:
- Verify the bot: `bin/tg_api.py getMe`
- Send a message: `echo '{"chat_id":"123","text":"hi"}' | bin/tg_api.py sendMessage -`
- Read updates: `bin/tg_api.py getUpdates`

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

The token is injected into the URL path (`/bot<token>/METHOD`) by the egress proxy, which matches the **raw, unencoded** `hsurr:...` surrogate. Do NOT URL-encode the surrogate — the stock `url_with_surrogate_path_segment()` helper encodes `:` as `%3A`, which breaks the proxy match and yields Telegram 404s. `bin/tg_api.py` does the substitution manually; keep it that way.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.telegram`.

## Operating Rules
1. Use this skill when the user asks for Telegram or this provider's API.
2. Restrict authenticated requests to: api.telegram.org.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.
5. Sending messages to chats needs the user's direction — never broadcast unprompted.
