---
name: "pump-stream"
description: "Access the pump.musebook.trade token stream: the $CLAWD holder-gated live Pump + Stonk feed. Challenge/verify wallet auth (user signs in their own wallet), then read tokens, launches, and the live stream. Also covers the public no-auth launch relay."
---

# Pump Stream

The live token stream behind `pump.musebook.trade` (Musebook **PUMP LIVE**):
new Pump.fun + Stonk.fun tokens as they launch, with metadata, links, and
market context. Two tiers:

| Tier | Endpoint | Auth |
|---|---|---|
| **public** | `wss://clawd-ws.fly.dev/ws` | none — raw launch feed |
| **holder** | `https://pump.musebook.trade` (→ Railway app) | any positive `$CLAWD` balance |

`$CLAWD` mint: `8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump`

## Public tier (no auth)

The relay WebSocket carries `token-launch` frames (name, symbol, mint,
creator, signature, metadata/image URIs, description, marketCapSol,
website/twitter/telegram, isV2). See the `pumpfun-live` skill for the
listener (`listen.mjs`). Use it when you just need the firehose.

## Holder tier (richer stream)

`GET /auth/policy` (no auth) shows the gate — currently **any positive
$CLAWD balance** unlocks access.

### Authenticate (user signs, agent never holds keys)

```bash
# 1. Get the challenge for the user's wallet
python3 bin/pump_stream.py challenge --wallet <WALLET_PUBKEY>
# -> {challenge_id, message}

# 2. The USER signs the exact message in their wallet
#    (Phantom/Solflare/Backpack signMessage, utf8 — NOT a transaction)

# 3. Verify and save the session
python3 bin/pump_stream.py verify --wallet <WALLET_PUBKEY> \
  --challenge-id <ID> --signature <BASE64_SIG>
# -> session cookie stored at ~/.pump-stream/session.json (0600)
```

The session is a cookie jar, not a private key. It expires — on 401s,
re-run challenge + verify.

### Read the stream

```bash
python3 bin/pump_stream.py tokens --limit 20     # latest stream tokens
python3 bin/pump_stream.py launches --limit 20   # recent launches
python3 bin/pump_stream.py stream --seconds 120  # poll the live feed
```

## Agent guidance

- The holder stream is **observation**: new tokens, metadata, socials.
  It is not a trading signal by itself — pair it with on-chain verification
  (Helius RPC: supply, authorities, largest holders) and the `rug-check`
  skill before acting on anything.
- Throughput is high at peak. Filter (`--limit`, match on name/symbol)
  rather than dumping the raw feed into context.
- Never ask the user for their seed phrase or private key. The auth flow
  is message-signing only; a transaction signature is never required and
  should be refused if the site ever asks for one.
- `PUMP_STREAM_BASE` env overrides the base URL (default
  `https://pump.musebook.trade`) — useful if the Railway origin changes.
