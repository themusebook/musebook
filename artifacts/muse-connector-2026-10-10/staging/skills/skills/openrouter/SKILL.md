---
name: "openrouter"
description: "Use OpenRouter when the agent needs LLM inference (chat, research, content) through the user's connected OpenRouter key."
---

# OpenRouter

## Purpose
LLM inference for the agent: chat completions, research, content generation, and model fallback — through the user's connected `custom.openrouter` credential. OpenAI-compatible API.

## Setup
The user connects once via the secure card (`credentials.request_api_access`, provider `openrouter`, api_key, `openrouter.ai`, `bearer_header`). They get the key at openrouter.ai/keys. Never ask for the raw key in chat.

## Usage
- Base: `https://openrouter.ai/api/v1`
- Auth: `Authorization: Bearer <key>` via the connector surrogate — never hardcode the key.
- Chat completions: `POST /chat/completions` with `{model, messages}` (OpenAI shape).
- Free-tier models exist (e.g. `:free` suffixed models) for zero-cost inference.
- List models: `GET /models`.

## Rules
- The key is capability, not authority: it buys inference, nothing else.
- Never print, log, or persist the key. Route it through the connector surrogate helpers only.
- Model choice is the operator's policy; default to whatever the operator configured.

## Musebook app attribution
Every OpenRouter request made by Musebook code sends app-attribution headers so usage aggregates under the **Musebook** app on [openrouter.ai/rankings](https://openrouter.ai/rankings) (app page: `openrouter.ai/apps?url=https://musebook.trade`). Verified 2026-09-20: these headers do not affect Bearer auth, including from Cloudflare Workers.

- `HTTP-Referer: https://musebook.trade`
- `X-OpenRouter-Title: Musebook`
- `X-OpenRouter-Categories: personal-agent,general-chat`
- Visibility is public (default) — no `X-OpenRouter-App-Visibility` header.

## Per-surface free models (2026-09-20)
Each Musebook surface uses a different free model ("character"), overridable via the named plain-text worker binding:

| Surface | Default model | Override binding |
|---|---|---|
| clawd-mail email auto-reply | `nvidia/nemotron-3.5-lightning:free` | `OPENROUTER_MODEL` |
| Site chat (`/api/chat`) | `z-ai/glm-5.2:free` | `OPENROUTER_CHAT_MODEL` |
| Agent chat (`/api/agent/chat`) | `nex-agi/nex-n2.5-pro:free` | `OPENROUTER_AGENT_CHAT_MODEL` |
| Agent draft (`/api/agent/draft`) | `qwen/qwen3.8-27b:free` | `OPENROUTER_AGENT_DRAFT_MODEL` |
| Town NPC dialogue | `google/gemma-4-31b-it:free` | `TOWN_RESIDENT_MODEL` |

Call sites: `~/workspace/musebook/cloudflare/worker.js` (musebook-proxy), `~/workspace/musebook/cloudflare/clawd-mail/worker.js`, and `bin/or_chat.py` in this skill. Pick replacements from `GET /models` entries ending in `:free` — availability changes over time, so re-check before swapping.
