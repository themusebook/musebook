---
name: "massive"
description: "Use Massive when the user asks for Massive, massive.com, or this provider's API (U.S. stock market data — formerly Polygon.io)."
---

# Massive (massive.com)

U.S. stock market data API: real-time/historical prices, aggregates, reference
data, technical indicators, news, short interest, and SEC filings. Formerly
Polygon.io.

## Purpose
Use Massive with the user-connected `custom.massive` credential.

## Tooling
Add service-specific CLIs under `~/workspace/skills/massive/bin/`.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and call `url_with_surrogate_query_param(...)` before authenticated requests (the key rides the `apiKey` query param). They must send only `hsurr:*` values, and only to the hosts below.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.massive`.

## Operating Rules
1. Use this skill when the user asks for Massive, massive.com, or stock market data via this provider's API.
2. Restrict authenticated requests to: api.massive.com.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.

## CLI
`bin/massive.py GET <PATH> [--param name=value] ...` — attaches the stored
`custom.massive` credential as the `apiKey` query param via authd surrogate exchange.

```bash
bin/massive.py GET /v1/marketstatus/now
bin/massive.py GET /v2/aggs/ticker/AAPL/prev
bin/massive.py GET '/v2/aggs/ticker/AAPL/range/1/day/2026-09-01/2026-09-23'
bin/massive.py GET /v3/reference/tickers --param ticker=AAPL --param limit=1
bin/massive.py GET /v1/indicators/rsi/AAPL --param timespan=day --param window=14
```

## Endpoint catalog (verified against provider docs 2026-09-23)
All paths are relative to `https://api.massive.com`. Match the task to the
right endpoint before calling.

| Need | Endpoint |
|---|---|
| Market status now | `GET /v1/marketstatus/now` |
| Upcoming market holidays | `GET /v1/marketstatus/upcoming` |
| Previous day OHLC + volume | `GET /v2/aggs/ticker/{ticker}/prev` |
| Custom OHLC bars | `GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}` |
| Daily market summary (all stocks, one date) | `GET /v2/aggs/grouped/locale/us/market/stocks/{date}` |
| Daily open/close for a ticker | `GET /v1/open-close/{ticker}/{date}` |
| Ticker overview (CIK, mcap, industry, branding) | `GET /v3/reference/tickers/{ticker}` |
| All tickers (active/inactive) | `GET /v3/reference/tickers` |
| Related companies | `GET /v1/related-companies/{ticker}` |
| SMA / EMA / MACD / RSI | `GET /v1/indicators/{sma,ema,macd,rsi}/{ticker}` |
| Ticker news + sentiment | `GET /v2/reference/news?{ticker=...}` |
| Short interest | `GET /stocks/v1/short-interest?{ticker=...}` |
| Short volume | `GET /stocks/v1/short-volume?{ticker=...}` |
| Free float | `GET /stocks/vX/float?{ticker=...}` |
| IPOs | `GET /vX/reference/ipos` |
| Splits | `GET /stocks/v1/splits` |
| Dividends | `GET /stocks/v1/dividends` |
| Exchanges | `GET /v3/reference/exchanges` |
| EDGAR filing index | `GET /stocks/filings/vX/index` |
| 10-K sections / 8-K text | `GET /stocks/filings/10-K/vX/sections`, `/stocks/filings/8-K/vX/text` |
| Form 3 / Form 4 (insiders) | `GET /stocks/filings/vX/form-3`, `/stocks/filings/vX/form-4` |
| 13-F holdings | `GET /stocks/filings/vX/13-F` |

## Endpoints NOT on the free Stocks Basic plan (do not retry-loop)
All `/v2/snapshot/...` endpoints (single ticker, full market, gainers/losers),
`/v3/snapshot`, `/v3/trades/{ticker}`, `/v2/last/trade/{ticker}`,
`/v3/quotes/{ticker}`, `/v2/last/nbbo/{ticker}`, and all
`/stocks/financials/v1/*` (balance sheets, cash flow, income, ratios).
Mark the field unavailable; the user would need a paid plan or the
Financials & Ratios expansion.
