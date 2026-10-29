---
name: "paybox"
description: "Use PayBox when the agent needs payments or funding rails. OAuth 2.1 device flow, MCP at api.paybox.sh."
---

# PayBox

## Purpose
Agent payments and funding rails. No API key — PayBox uses OAuth 2.1 (device flow). Connected via the `paybox` workspace tooling, not a standard custom connector card.

## Connection (device flow)
1. Make sure the PayBox CLI is installed: `npm i -g @paybox-sh/sdk` (binary: `paybox`).
2. Run the device login helper: `node ~/workspace/paybox/device_login.mjs`. It prints a code and a URL.
3. The user approves the code at the shown URL in their browser.
4. Tokens land in `~/.config/paybox/config.json` (mode 0600). Access tokens are short-lived (~60 min); refresh tokens rotate with a ~30-day sliding lifetime.
5. MCP endpoint: `https://api.paybox.sh/mcp`. OAuth issuer: `https://api.paybox.sh`.

## Key rotation
If the signing key is ever exposed, rotate it immediately at the agent-key page (`https://app.paybox.sh/agent-key?client_id=<your-client-id>`) and merge the replacement with `node ~/workspace/paybox/merge_signing_key.mjs`. The replacement must be captured through verified secure secret entry — never chat, argv, logs, or screenshots.

## Write safety
- Every payment, transfer, or funding action needs the user's explicit approval of exact terms first. No grant — including "autonomous" — skips this.
- Inspect status envelopes on writes. Never repeat a write to "finish" it — poll `get_request(request_id)` instead.
- On-chain PayBox `success` means confirmed. Report the receipt.

## Rules
- Never print, log, or persist raw tokens or signing keys.
- Config file stays 0600. Secrets never go in prompts, repos, or telemetry.
