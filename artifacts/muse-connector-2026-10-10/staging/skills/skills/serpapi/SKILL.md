---
name: "serpapi"
description: "Structured Google/Bing/Yahoo search results via SerpApi: organic results, knowledge graph, answer boxes, AI Overviews, news, maps, shopping. Use for real-time web research, news lookups, and SERP data. Connector custom.serpapi."
---

# SerpApi

## Purpose
Run structured web searches through SerpApi (`https://serpapi.com/search?engine=google` by default) and return them as clean JSON. Engines: `google`, `google_news`, `google_scholar`, `google_maps`, `google_finance`, `google_shopping`, `bing`, `duckduckgo`, `yahoo`, `youtube`, `google_trends`, `google_patents`, and more (https://serpapi.com/playground).

## Tooling
CLI: `~/workspace/skills/serpapi/bin/serp.py` — surrogate-authenticated against the `custom.serpapi` connector.

```bash
# Web search (default google engine, 10 results)
serp.py search --q "solana token launches today" --num 10

# News search
serp.py search --q "solana ETF" --engine google_news --num 5

# Localized results
serp.py search --q "best sushi" --location "Austin, Texas" --engine google_maps

# Full raw SerpApi JSON (large)
serp.py search --q "example" --raw

# Quota / plan check (free, does not consume a search)
serp.py account
```

Output is normalized: `organic_results` (title/link/snippet/position/source), `answer_box`, `knowledge_graph`, `ai_overview`, `related_questions`, `local_results`, `shopping_results`. Use `--raw` for the complete SerpApi payload.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.serpapi`.

## Operating Rules
1. Use this skill when the user asks for SerpApi, structured search results, or SERP data.
2. Restrict authenticated requests to: serpapi.com.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.
5. Cached searches (same query + params within an hour) are free; plan quota is monthly — check `serp.py account` before heavy runs.
