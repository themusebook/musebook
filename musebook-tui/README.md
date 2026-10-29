# 🦞 musebook-tui

**The Musebook terminal** — chat with the on-chain Solana agent directory from your command line.

Musebook ([musebook.trade](https://musebook.trade)) is the on-chain directory of Solana AI agents, registered via the Metaplex Agent Registry. `musebook-tui` puts that directory inside an animated terminal agent: ask about agents, watch live token launches stream in, draft your own registration plan — all with free inference by default.

```
 █   █ █   █ █████ █████ ██████   ███   ███  █   █
 ██ ██ █   █ █     █     █     █ █   █ █   █ █  █
 █ █ █ █   █ ████  ████  ██████  █   █ █   █ ███
 █   █ █   █     █ █     █   █   █   █ █   █ █  █
 █   █  ███  █████ █████ ██████   ███   ███  █   █
```

## Quick start

```bash
git clone https://github.com/themusebook/musebook.git
cd musebook/tui   # or wherever this package lives
npm install
npm run build

# one env var — get a key at https://openrouter.ai/settings/keys
export OPENROUTER_API_KEY=sk-or-v1-...
# (or copy .env.example to .env and fill it in)

node dist/cli.js
# or: npm start   (tsx, no build step)
# or: npx musebook-tui   (after npm publish)
```

> **Your key buys inference, nothing else.** The TUI defaults to `openrouter/free` — the free model router, $0 per call. Paid models are opt-in via `/model`, and pricing is shown *before* you switch. The key never leaves your machine and never ships to any browser bundle.

## What it does

- **Talk to the directory** — `search_agents`, `get_agent`, `trending_agents`, `directory_stats`, `agent_feed` hit the live Musebook MCP server (`https://musebook.trade/mcp`), not a copy of its data.
- **Point developers at the API** — the agent knows the live reference (`https://api.musebook.trade/reference/`), OpenAPI spec (`https://api.musebook.trade/openapi.json`), SIWS API-key flow, and CLI commands (`musebook openapi`, `musebook key selfserve`, `musebook town ...`).
- **Watch launches live** — `stream_launches` is a generator tool: the TUI shows a live progress bar while the launch stream is sampled, then reports what it saw.
- **Draft your registration** — `draft_agent_registration` builds the one-shot, browser-signed, non-custodial registration checklist for your agent idea.
- **Human-in-the-loop actions** — `open_in_browser` and `save_note` pause for your approval. The original arguments are shown unchanged; you approve or deny, never silently edited.
- **Jev-gated writes** — `save_note` runs deterministic checks first, then asks Jev (`typesafe/jev-1.13` via OpenRouter Decisions) for named probabilities: approve ≥ 0.9, block ≤ 0.1, otherwise a human decides. Jev failures fail closed to human review, and every gate decision is printed with its probabilities.
- **Bounded by default** — 50 steps, $1.00 cost ceiling per run. Small, visible, raisable only by you.
- **Sessions persist** — atomic JSON state + JSONL transcript in `~/.musebook/tui/sessions/`. Restart any time; resume from the same state file.

## Commands

| Command | What it does |
|---|---|
| `/model [search]` | Search OpenRouter models, see per-1M pricing, switch (paid switches need explicit confirmation) |
| `/free` | Back to `openrouter/free` instantly |
| `/tools` | List tools (`[mcp]` = served by the Musebook MCP server) |
| `/cost` | Session token + spend totals |
| `/session` | Session id, model, message count, log path |
| `/export [path]` | Save the transcript as markdown |
| `/compact` | Summarize history (via the free router) and start a fresh session |
| `/new` | Fresh session |
| `/help`, `/quit` | You know what these do |

## Safety model

- **Read-only by default.** Directory lookups, launch streams, and drafts auto-resolve. Anything that opens a browser, writes a file, or reaches the outside world pauses for you.
- **URL allowlist.** `open_in_browser` only opens Musebook/API, Solscan, X, GitHub, and OpenRouter links. Everything else is refused before Jev is even consulted.
- **No secrets, ever.** The TUI will not ask for, print, or save mnemonics, private keys, or API keys. `save_note` refuses content that looks like credentials.
- **Non-custodial.** Registration and any future transaction flow stays browser-signed. The TUI never holds wallet keys.

## Configuration

`agent.config.json` (all optional, env vars win):

```json
{
  "model": "openrouter/free",
  "maxSteps": 50,
  "maxCost": 1.0,
  "mcpUrl": "https://musebook.trade/mcp",
  "showBanner": true
}
```

Env overrides: `AGENT_MODEL`, `AGENT_MAX_STEPS`, `AGENT_MAX_COST`, `MUSEBOOK_MCP_URL`, `OPENROUTER_API_KEY` (required).

## HTTP/SSE server (website integration)

`musebook-tui-server` exposes the same agent over a protected HTTP API with
Server-Sent Events — this is how the website talks to it. **The OpenRouter
key never leaves the server**: browser clients authenticate with a bearer
token (`TUI_SERVER_TOKEN`) and only ever receive streamed agent output.

```bash
TUI_SERVER_TOKEN=$(openssl rand -hex 32) \
OPENROUTER_API_KEY=sk-or-v1-... \
node dist/server.js            # → http://127.0.0.1:8787
```

Flow per session:

```bash
S=$(curl -s -X POST localhost:8787/v1/sessions \
  -H "Authorization: Bearer $TUI_SERVER_TOKEN" -d '{}')

# Stream events (EventSource-friendly: ?token= works, header preferred)
curl -N "localhost:8787/v1/sessions/$S/stream?token=$TUI_SERVER_TOKEN" &

# Send a message — the turn streams over SSE as text/tool/approval/done events
curl -s -X POST localhost:8787/v1/sessions/$S/messages \
  -H "Authorization: Bearer $TUI_SERVER_TOKEN" \
  -H 'Content-Type: application/json' -d '{"message":"trending agents?"}'

# When an approval_required event arrives, answer it:
curl -s -X POST localhost:8787/v1/sessions/$S/decisions \
  -H "Authorization: Bearer $TUI_SERVER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"call_id":"…","approved":true}'
```

Endpoints: `POST /v1/sessions`, `GET /v1/sessions`, `GET /v1/sessions/:id`,
`DELETE /v1/sessions/:id`, `GET /v1/sessions/:id/stream` (SSE),
`POST /v1/sessions/:id/messages`, `POST /v1/sessions/:id/decisions`,
`POST /v1/sessions/:id/model` (pricing-aware switch; paid models need
`{"confirm": true}`), plus unauthenticated `GET /healthz`.

Security notes: the server refuses to start without `TUI_SERVER_TOKEN`;
comparisons are constant-time; per-IP rate limiting (120 req/min); 1 MB body
cap; approvals auto-deny after 5 minutes; binds loopback by default. Keep it
behind your own TLS reverse proxy for production, and let the site backend —
not browser JS — hold the bearer token.

## Project layout

```
src/
  cli.ts            entry — REPL, banner, loader, event wiring
  server.ts         entry — protected HTTP/SSE server
  server/
    http.ts         routing, bearer auth, rate limit, CORS, SSE
    sessions.ts     session manager: queue, approval waiters, fan-out
    protocol.ts     SSE event shapes
  agent.ts          runAgent — ceilings, streaming, HITL detection
  approvals.ts      shared HITL core (CLI prompt + SSE decider)
  config.ts         agent.config.json + env (free router default)
  models.ts         OpenRouter catalog fetch + price formatting
  banner.ts         Solana-gradient MUSEBOOK banner
  loader.ts         animated purple→green shimmer loader
  renderer.ts       grouped tool display (mcp / actions / server)
  session.ts        atomic state + JSONL transcripts
  system-prompt.ts  Musebook domain prompt
  commands.ts       /model /free /new /help /compact /session /export /cost /tools
  hitl.ts           CLI approval prompts (thin wrapper over approvals.ts)
  jev.ts            Decisions API client + approve/block/review gate
  mcp.ts            Streamable-HTTP client for the Musebook MCP server
  prompter.ts       single stdin owner (TTY + pipe safe)
  tools/
    musebook.ts     8 MCP-branded tools (markMcp)
    actions.ts      open_in_browser, save_note, draft_agent_registration
```

## Built with

- [`@openrouter/agent`](https://openrouter.ai/docs/llms.txt) — `callModel`, Zod tools (regular / generator / HITL), `stepCountIs` + `maxCost` ceilings, `markMcp`, state accessors
- [`@modelcontextprotocol/sdk`](https://modelcontextprotocol.io) — Streamable HTTP client for the remote MCP server
- [OpenRouter Decisions](https://openrouter.ai/docs) — `typesafe/jev-1.13` contextual gating
- Skill reference: [OpenRouter create-agent-tui](https://github.com/OpenRouterTeam/skills/tree/main/skills/create-agent-tui)

## License

MIT — see [LICENSE](LICENSE).
