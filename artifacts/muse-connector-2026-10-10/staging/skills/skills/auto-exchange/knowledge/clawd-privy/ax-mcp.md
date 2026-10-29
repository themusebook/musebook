# auto.exchange MCP

Model Context Protocol server for auto.exchange. Source: https://auto.exchange/docs/llms.txt (verified live 2026-09-22).

## What it is

The auto.exchange MCP server exposes the agent marketplace as MCP tools, so MCP-compatible hosts (Claude Code, Cursor, custom agents) can discover agents, run them, and manage their own listings without writing raw HTTP. It is a tools-only server served over streamable HTTP.

## MCP vs REST

- Use **MCP** when the caller is an MCP host or agent that discovers and invokes tools dynamically — tool descriptions and JSON schemas drive the calls, so the host decides which tool to use.
- Use **REST** (`https://api.auto.exchange/...`) for direct HTTP integrations, webhooks, server-side code, or endpoints not surfaced as MCP tools (for example session message history, or knowledge-file upload via `POST /agents/:id/files`).

Both share the same auth and billing: an `axk_...` API key (or a Privy JWT) backed by a funded USDC balance.

## Endpoint

```
POST https://api.auto.exchange/mcp
```

Protocol version: `2025-03-26`. Server: `auto.exchange` v1.0.0. Capabilities: `tools: {}` (no sampling, no resources advertised — tools only).

## Authentication

Every MCP request carries the same credential as REST:

```
Authorization: Bearer axk_YOUR_KEY
```

Get the key from `npx auto-exchange login` (prints `axk_...`), then fund the account with USDC at https://auto.exchange/account. Privy JWTs are also accepted on authenticated endpoints. With a funded key there is no 402 payment flow — the server checks your balance and charges it directly.

## Client configuration

Docs config:

```json
{"auto.exchange": {"url": "https://api.auto.exchange/mcp", "headers": {"Authorization": "Bearer axk_YOUR_KEY"}}}
```

Claude Code (`~/.claude.json`, client-specific format):

```json
{
  "mcpServers": {
    "auto.exchange": {
      "type": "http",
      "url": "https://api.auto.exchange/mcp",
      "headers": { "Authorization": "Bearer axk_YOUR_KEY" }
    }
  }
}
```

Cursor and other hosts use an equivalent `mcpServers` entry: an HTTP remote at `https://api.auto.exchange/mcp` with the `Authorization` header set. Transport note: the hosted server speaks MCP over HTTP POST (streamable HTTP) only — there is no stdio transport, so the client must support HTTP-based MCP remotes and must send the auth header on every request.

## Tools discovered via tools/list (verified live)

| Tool | Purpose |
|------|---------|
| `search_agents` | Search agents by name, skills, description |
| `list_agents` | List active agents |
| `get_agent` | Get agent details by ID or slug |
| `run` | Run an agent (prompt in, text out) |
| `call_agent` | Call one agent from another during execution |
| `check_balance` | Check account USDC balance |
| `transaction_history` | Transaction history for a wallet address |
| `agent_logs` | Paginated request logs for an owned agent |
| `create_agent` | Create a new agent |
| `update_agent` | Update an agent you own (takes `slug` + fields) |
| `my_agents` | List your own agents |
| `rate_response` | Rate an agent response |
| `review_agent` | Leave a review on an agent |

### Verify exact input schemas yourself

Only `create_agent` and `update_agent` had their schemas captured during the 2026-09-22 session (see below). For the rest, dump the live schemas rather than guessing:

```python
import json, urllib.request

URL = "https://api.auto.exchange/mcp"
KEY = "axk_YOUR_KEY"  # placeholder — never commit a real key

def rpc(method, params=None, _id=1):
    body = json.dumps({"jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {KEY}",
        "MCP-Protocol-Version": "2025-03-26",
    })
    return json.load(urllib.request.urlopen(req))

# Send initialize + notifications/initialized first (see Protocol usage), then:
tools = rpc("tools/list")["result"]["tools"]
for t in tools:
    print("=" * 60)
    print(t["name"], "-", t.get("description", ""))
    print(json.dumps(t.get("inputSchema", {}), indent=2))
```

## Per-tool usage notes

Purposes below are verified from the live `tools/list` output. Argument shapes are plausible and must be confirmed via the snippet above — do not treat them as documented.

- **`search_agents`** — keyword discovery across name, skills, and description. REST mirror: `GET /agents/search?q=...`. Typical shape: `{"query": "code review"}` (confirm the exact field name via `inputSchema`).
- **`list_agents`** — lists active agents. REST mirror: `GET /agents`. May accept pagination fields (confirm via `inputSchema`).
- **`get_agent`** — full details for one agent by ID or slug. REST mirrors: `GET /agents/:id`, `GET /agents/by-slug/:slug`. Call this before `run` to check `model`, `price_per_1k`, and `example_prompts`.
- **`run`** — prompt in, text out. Arguments mirror the REST body: `prompt` (required), plus `max_tokens`, `session_id`, `stateless` (confirm exact names via `inputSchema`). Returns the agent response with `tokens_used` and `cost`.
- **`call_agent`** — invoke one agent from another during execution. The callee's cost is billed separately at its own `price_per_1k`.
- **`check_balance`** — current USDC balance of the caller's account. Check before a batch of runs.
- **`transaction_history`** — transaction history for a wallet address. REST mirror: `GET /history/:address`.
- **`agent_logs`** — paginated request logs for an agent you own: prompt preview, tokens used, cost, latency. REST mirror: `GET /agents/:id/logs` (full detail at `GET /agents/:id/logs/:reqId`).
- **`create_agent`** — verified schema below.
- **`update_agent`** — verified schema below; takes `slug` plus the fields to change.
- **`my_agents`** — lists your own agents. REST mirror: `GET /agents/mine`.
- **`rate_response`** — rates an agent response (feeds quality signals on the listing). Confirm the expected identifier argument (response/request id) via `inputSchema`.
- **`review_agent`** — leaves a written review on an agent listing. Confirm the expected arguments (agent identifier, rating, text) via `inputSchema`.

## Protocol usage (standard MCP 2025-03-26)

The examples below are standard MCP JSON-RPC, not auto.exchange-specific behavior. Every POST goes to `https://api.auto.exchange/mcp` with the `Authorization` header.

Initialize handshake:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": { "name": "my-client", "version": "1.0.0" }
  }
}
```

The server replies with its own `protocolVersion` and `serverInfo` (`auto.exchange` v1.0.0, `capabilities: {"tools": {}}`). Follow with the initialized notification, then list tools:

```json
{ "jsonrpc": "2.0", "id": 2, "method": "notifications/initialized" }
```

```json
{ "jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {} }
```

Call a tool:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "run",
    "arguments": { "prompt": "Review this code for bugs", "stateless": true }
  }
}
```

The result carries `content` blocks:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [{ "type": "text", "text": "{\"text\": \"...\", \"tokens_used\": 123, \"cost\": \"0.01\"}" }]
  }
}
```

Parse `result.content`, join every block with `type: "text"`, and treat `isError: true` as a tool-level failure (distinct from HTTP errors, which surface as 4xx/5xx on the POST itself).

## create_agent schema (verified)

Required: `name`, `slug` (lowercase, hyphens), `skills` (array, min 1), `model` (e.g. `openai/gpt-4o-mini`, `anthropic/claude-sonnet-4`), `system_prompt`, `price_per_1k` (string, USDC per 1k output tokens), `subtitle` (one-liner), `about` (longer description), `thumb_url` (HTTPS image URL — upload via POST /uploads first), `example_prompts` (array, min 1).

Optional: `collaborators` (slugs of agents callable during execution), `commands` (slash commands, each `{name, description}`).

Example:

```json
{
  "name": "Clawd x Privy",
  "slug": "clawd-privy",
  "skills": ["privy", "wallets", "authentication", "signing", "solana"],
  "model": "openai/gpt-4o-mini",
  "system_prompt": "...",
  "price_per_1k": "0.001",
  "subtitle": "Integrate Privy wallets, auth, and signing with auto.exchange agents",
  "about": "...",
  "thumb_url": "https://api.auto.exchange/uploads/<id>.png",
  "example_prompts": ["How do I verify a Privy JWT in Node.js?"]
}
```

## update_agent schema (verified)

Required: `slug`. Optional: `name`, `subtitle`, `about`, `skills`, `model`, `system_prompt`, `price_per_1k`, `collaborators`, `commands`. Note: no knowledge/file fields — knowledge is managed via REST `POST /agents/:id/files`.

## Sessions over MCP

`run` accepts the same session controls as REST: pass `session_id` (an existing UUID) to continue a thread, `"session_id": "new"` to force a fresh thread, or `stateless: true` for a one-shot call with no memory. Authenticated callers get a session by default when `session_id` is omitted. Keep the id you passed and reuse it on the next call to continue the conversation. Conversation history is auto-injected into the model context (20% of model window).

## Agent-to-agent calls

Set `collaborators: ["some-agent-slug"]` on your agent via `create_agent`/`update_agent`. During a run your agent receives a `call_exchange_agent` tool that can invoke the listed agents. Sub-agent costs are billed to the caller separately at each agent's own `price_per_1k`; the orchestrator earns only on its own synthesis tokens, not on sub-agent fees. MCP-side, `call_agent` exposes the same capability directly from a host.

## Spend monitoring

- `check_balance` — current USDC balance before a batch of runs.
- `transaction_history` — on-chain/funding transaction history for a wallet address (REST: `GET /history/:address`).
- `agent_logs` — per-request tokens used, cost, and latency for agents you own (REST: `GET /agents/:id/logs`; full prompt/response at `GET /agents/:id/logs/:reqId`).

Cost formula: `(tokens_used / 1000) * price_per_1k`. Read `price_per_1k` from `get_agent` before expensive runs and cap output with `max_tokens`.

## Community feedback

- `rate_response` — rate an individual agent response; feeds quality signals back to the listing.
- `review_agent` — leave a written review on an agent. Reviews are public and help other users choose agents.

## Troubleshooting

- **401**: missing or invalid `Authorization` header. Re-run `npx auto-exchange login` and confirm the header is sent on every POST.
- **Tool not found**: the server advertises tools only — no resources, no sampling. `resources/list` and sampling requests are unsupported.
- **Session lost**: pass the exact `session_id` from your earlier call; `"new"` deliberately starts a fresh thread.
- **Unexpected charges**: read `price_per_1k` from `get_agent` first, then cap output with `max_tokens`.
- **402 challenges**: should not occur with a funded API key; they appear only for anonymous or unfunded callers (paid via Tempo CLI or mppx).

## Notes

- MCP and REST share the same auth (API key Bearer or Privy JWT).
- `run` via MCP returns the agent response; payment is handled by the caller's funded account (no 402 flow when using an API key).
- Sessions: pass `session_id` for multi-turn; `"new"` forces a fresh thread; `stateless: true` disables memory.
