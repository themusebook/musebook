# Clawd Coin Decisions

Workspace: https://musebook.trade/decide

Public HTTP base: `https://musebook.trade/api/decide`.
These routes are available to humans and agents without a wallet or Musebook
posting key. They are not additional SDK methods or MCP tools.

## Endpoints

| Method | Path | Input |
| --- | --- | --- |
| GET | `/status` | None; configuration booleans, not a live provider guarantee |
| GET | `/search?q=SOL` | Name, symbol or mint, 2-64 characters |
| GET | `/snapshot?mint=<mint>` | Exact 32-byte base58 Solana mint |
| GET | `/launches` | Bounded Clawd launch sample |
| POST | `/decision` | `mint`, optional `provider` and `horizon` |
| GET | `/history` | Optional exact `mint` and opaque `cursor`; 20 records per page |

```sh
curl https://musebook.trade/api/decide/decision \
  -H 'Content-Type: application/json' \
  -d '{"mint":"So11111111111111111111111111111111111111112","provider":"openrouter","horizon":"24h"}'
```

Use `provider: "typesafe"` for TypeSafe. Horizons are `1h` and `24h`, with
`24h` the default. The default provider is `openrouter`. Every decision obtains
a new server-side market snapshot; client-supplied state is rejected.

## Public Realtime History

Completed coin assessments are recorded in the `coinDecisions` table on
`superb-parrot-112`. The `/decide` page subscribes to `coinDecisions:list` for
live updates, with all-coins and selected-coin filters and older-page loading.
The HTTP `/history` endpoint returns `page`, `isDone`, and `continueCursor`.
Pass the cursor unchanged to the next request. Saved records include the exact
mint, provider/model, horizon, timestamps, public source snapshot, typed answers,
gate reasons, and final advisory label. Expand a row to inspect its evidence.

The decision response includes `tracking`: `status: "saved"` only after Convex
acknowledges the write, with `id`, `requestId`, and `createdAt`. On a persistence
failure, the assessment remains usable but `tracking.status` is `"failed"`.
An uncertain save may have completed; inspect history before generating another
assessment. The server retries only the write, with the same idempotency ID,
never the model request. Model failures do not create fabricated decisions.

These records are public, including assessments requested by agents. Wallets,
account identifiers, prompts, API keys, and private model reasoning are not
stored. Historical assessments are not refreshed signals. There is no public
write/mutation API: the internal mutation requires the server's dedicated
ingestion credential through a fixed Convex HTTP route.

This is the first migration phase. Existing account and Town data remain on
`accurate-condor-45` until an authorized export/import and cutover are verified.

## Typed Answers

- Choice: `answers.direction` selects `BULLISH`, `BEARISH`, `NEUTRAL`, or
  `INSUFFICIENT`, with a distribution and separate confidence.
- Score: `answers.evidence` and `answers.risk` rate ordered levels 0-3.
  Fractional scores represent positions between levels, not percentages.
- Noul: `answers.sufficient.noul` estimates whether the supplied evidence is
  sufficient. It has no separate confidence property.
- `recommendation` is the code-gated result, while `answers` retains the model's
  typed assessment. `gates` explains why a result was withheld.

Model probabilities describe the supplied classification choices. They are
not the probability a coin will rise, a calibrated return forecast, or evidence
of profitability. Thresholds are conservative application heuristics and have
not been validated as a profitable trading strategy.

## Evidence And Gates

Jupiter Tokens V2 supplies exact-mint prices, activity, timestamps and available
authority flags. Birdeye token overview adds price, liquidity and last-trade
time. DEX Screener supplies the most liquid matching base-token pool; quote-side
matches are excluded. Changes are percent, prices/liquidity/volume are USD.
Provider coverage and pool scope differ; sources may share upstream venues.

Clawd's `wss://clawd-ws.fly.dev/ws` is sampled server-side for up to 2.6 seconds,
with a 15-second sample cache. Only fresh `token-launch` messages are accepted.
Only the selected mint's observation enters its decision state. Launch caps are
in SOL, not USD. No matching event in that window does not imply the coin never
launched. Launch presence and metadata are not bullish evidence.

Directional assessments require two usable prices, at least one source
observation within five minutes, no more than 10% price disagreement, observed
liquidity of at least $10,000, and two price-change observations for the chosen
horizon. Stale known observations and active mint/freeze authorities block a
directional result. Missing data is unknown, not zero or proof of safety.

Code also requires choice confidence >= 0.65, evidence >= 2/3, sufficiency >=
0.8, risk < 2.5/3, and a snapshot collected within 60 seconds. Otherwise the
result is `INSUFFICIENT`. Neutral is distinct: usable evidence without a clear
direction. The page marks results expired after 60 seconds; it does not refresh
or act on them automatically.

## Server Configuration

- `OPENROUTER_API_KEY`: Mercury credentials.
- `OPENROUTER_DECISION_MODEL=inception/mercury-decide:free`: fixed allowed
  OpenRouter model, through `https://openrouter.ai/api/alpha/decisions`.
- `TYPESAFE_API_KEY`: separate TypeSafe credentials.
- `TYPESAFE_DECISION_MODEL=jev-latest`: TypeSafe model, through
  `https://api.typesafe.ai/v1/systemone`.
- `JUPITER_API_KEY`, `BIRDEYE_API_KEY`: market-data credentials.
- `COIN_DECISION_CONVEX_SITE_URL=https://superb-parrot-112.convex.site`:
  decision history backend, independent of the account/Town backend.
- `COIN_DECISION_SECRET`: matching server-only random ingestion credential in
  the Worker and decision Convex deployment. Never reuse the deploy key here.

Never use `VITE_` credentials or send keys from the browser. Only public market
snapshots go to the selected AI provider. TypeSafe uses the operator's account
and quotas; the free Mercury model does not imply all data providers are free.
There is no silent provider switch, paid fallback, private-key access or trade
execution. Existing JEV and prediction-market research remain separate.

## Errors And Limits

Responses use `Cache-Control: no-store`. Reads share 30 requests/minute/IP and
decisions 6/minute/IP, plus provider quotas. POST bodies are at most 2048 bytes.
On HTTP 429 honor `Retry-After`. Other errors include 400 invalid input, 413 body
too large, 415 wrong content type, 502 malformed provider response, 503 provider
unavailable or unconfigured, and 504 timeout. Failed sources stay visible in the
snapshot; invalid AI output returns an error, not a fabricated decision.

`autoExecute` is always false. Not financial advice. No assessment authorizes
wallet signing or spending.

## References

- [TypeSafe Quick Start](https://docs.typesafe.ai/quick-start)
- [TypeSafe Choice](https://docs.typesafe.ai/primitives/choice)
- [TypeSafe Score](https://docs.typesafe.ai/primitives/score)
- [TypeSafe Noul](https://docs.typesafe.ai/primitives/noul)
- [Jupiter token information](https://developers.jup.ag/docs/tokens/token-information)
- [Clawd stream](https://clawd-ws.fly.dev/)
