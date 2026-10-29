---
name: "openmarket-mcp"
description: "Use the OpenMarket chart MCP server (mcp.openmarket.xyz) when the user asks to inspect or change their OpenMarket charts, resolve symbols against the chart plane directory, manage alerts/watchlists, or run agent trading through their tab. Streamable HTTP + agent token."
---

# OpenMarket chart MCP

The chart-control plane behind openmarket.xyz charts: inspect workspaces,
switch symbols/timeframes, add indicators, create scratch charts, manage
alerts and watchlists, and (with `mcp:trade`) place orders through the user's
own browser tab. Authenticated with the user-connected `custom.openmarket-mcp`
agent token (Bearer header via authd surrogate).

## Token
Created by the user at `https://openmarket.xyz/chart/console/agents`. Access
levels: **read** (inspect), **chart** (chart changes), **trade** (execution
through their tab), plus an **Alerts and watchlists** add-on (`mcp:alerts`).
Scopes: `mcp:read`; `mcp:read mcp:chart`; `mcp:read mcp:chart mcp:trade`.
Never paste the token into chat or commit it; it lives only in the connector.

## Tooling
`bin/mcp.py` — minimal Streamable HTTP JSON-RPC client.

```bash
bin/mcp.py tools                       # list tools
bin/mcp.py call chart_status '{}'
bin/mcp.py call chart_list '{}'
bin/mcp.py call chart_refresh '{}'
bin/mcp.py call symbol_resolve '{"symbol":"BTC"}'
bin/mcp.py call chart_symbol '{"exchange":"BINANCE_FUTURES","symbol":"BTCUSDT"}'
```

## Auth
Nothing here collects the token. Never ask the user to paste it in chat or
set a secret environment variable. A 401/403 on a request that carried the
credential means the token is wrong or lacks the scope: `scope_insufficient`
(needed `mcp:chart` / `mcp:trade` / `mcp:alerts`) means the user must re-add
the token with that access level, or mint a new one at the agents console
page. The connector is stored as `custom.openmarket-mcp`.

## Operating rules (from llms.txt)
1. If the user names a chart they have open, call `chart_workspace_select`
   with that workspaceId first. Otherwise call `chart_list` and ask which
   chart they have open — never assume. The active workspace is only the last
   one any agent used with this key.
2. `chart_status {}` to check the connection and active workspace.
3. `chart_refresh {}` and report what you see: symbol, timeframe, indicators.
4. Offer one small visible change and wait for a yes (add an indicator,
   switch the timeframe). Make it, then say what changed so they can see it.
5. Read-only access inspects; chart changes require the `mcp:chart` scope.
6. `symbol_resolve` before `chart_symbol` when unsure of venue/ticker. It
   answers the exact exchange+symbol the chart plane lists, or named
   candidates — never guess. `unknown_market` returns up to 5 candidates;
   relay them, never retry the same pair. US stocks are POLYGON with
   `AAPL/USD` style symbols.
7. After `chart_symbol`, only `load: loaded` (with rowCount) means the pane
   shows data; `empty`/`error` carry the `empty_load` warning — say so, never
   describe the chart as showing the market.
8. Scratch charts (`chart_create` with `scratch: true`) expire 48h after last
   agent use (max 30 days); `chart_keep` makes one permanent.

## Execution through the tab (`mcp:trade`)
Orders are placed by the user's own browser tab within limits they set there.
The user must arm the agent: OpenMarket > Wallet > Agent trading, arm this
agent for the session. `no_arm` means they must do that first. Always pass
`idempotency_key` (1-64 chars: A-Z a-z 0-9 _ . : -); reuse the same key for
retries. `relay_uncertain` means the order may have executed — read
`account_orders` before retrying. Report the tab's status and reason verbatim
(submitted / filled / rejected / blocked / dry_run / pending_confirm / error).
**Standing rule: no order without the user's explicit approval of the exact
terms in chat.** Legacy unscoped keys have read+chart only, never trade.

## Alerts and watchlists (`mcp:alerts`)
Tools: `alert_create/list/update/pause/resume/delete/history`,
`watchlist_list/get/create/update/delete/add_symbols/remove_symbols`. Alerts
fire in the user's OpenMarket notifications (toast, optional email) whether or
not a chart is open. Watchlist refs are `EXCHANGE:SYMBOL` (e.g.
`HYPERLIQUID_FUTURES:SOL`).
