---
name: pulse-tweets
description: Scheduled tweet pulses for a Solana agent's X presence — rotating market-data tweets, Phoenix perps snapshots, and a token/project narrative rotator. Data-only, exactly-once per run, never advice.
version: 1.0.0
---

# Pulse Tweets

The three tweet pulses that keep an agent's X feed alive on a schedule.
Each script does one run = one post (or a clean silent skip), keeps its own
rotation state next to the script, and enforces the safety rules below.

## Scripts (`bin/`)

- **`market_tweet.py`** — rotating venue market-data tweets (Phoenix perps
  prices → Jupiter Forecast BTC rounds → DFlow SOL/USDC spot quote → Imperial
  multi-venue marks). One run posts ONE tweet from the first venue with fresh
  data. `--dry-run` prints without posting.
- **`phoenix_perps_pulse.py`** — Phoenix perps snapshot: BTC/SOL/ETH mark,
  24h change, open interest, funding. One data-only tweet per run.
  `--dry-run` prints without posting.
- **`token_rotation_tweet.py`** — YOUR narrative rotation. Create
  `rotation.json` next to the script:
  `{ "tweets": ["...", "..."] }` (each ≤ 280 chars). One run posts the next
  tweet in rotation. If X rejects a slot as duplicate content, the rotation
  advances past it instead of wedging.

## Prerequisites

- The `x-connect` skill with a connected X account (post.py handles the
  actual posting, blocklist, and 280-char enforcement).
- `market_tweet.py` venue CLIs need their connectors from the main skill's
  §1 flow: Jupiter (Pro API key) for the Forecast leg, DFlow (API key) for
  the spot-quote leg. Phoenix and Imperial legs are public, no key needed.
  A venue that isn't wired is simply skipped in rotation.
- Optional: set `$PULSE_FOOTER` for your own tagline appended to
  market/perps tweets (default: none). `$SKILLS_DIR` overrides the skill
  install location (default `~/.muse/skills`).

## Suggested schedules

| Pulse | Cadence | Command |
|---|---|---|
| Market tweets | hourly | `python3 ~/.muse/skills/pulse-tweets/bin/market_tweet.py` |
| Phoenix perps | hourly | `python3 ~/.muse/skills/pulse-tweets/bin/phoenix_perps_pulse.py` |
| Token rotation | hourly | `python3 ~/.muse/skills/pulse-tweets/bin/token_rotation_tweet.py` |

Stagger them (e.g. :05, :25, :45) rather than firing all three on the hour.
Start conservative — hourly is plenty; raise volume only deliberately.

## Rules every run obeys

1. **Exactly once per fire.** Never run the script twice for one schedule
   tick — a duplicate post must never happen.
2. **Data only.** Prices, marks, funding, round odds, shipped facts. No
   recommendations, no signals, no advice language, no price targets.
3. **Never invent tweet text** or bypass the scripts. The rotation files are
   the content source of truth.
4. **Silent on success** — log the posted URL in the run result, no chat
   noise. Report failures concisely (which step failed); do not retry a
   failed post yourself.
5. **Never touch wallets, trading, or credentials.** These scripts are
   read-only market data + one X post.

## Tests

- `python3 bin/market_tweet.py --dry-run` prints the composed tweet, posts nothing.
- `python3 bin/phoenix_perps_pulse.py --dry-run` same.
- `python3 bin/token_rotation_tweet.py` with no `rotation.json` exits with a
  helpful error and an example file shape.
