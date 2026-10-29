---
name: "stonkfun"
description: "Use Stonkfun when the user asks for Stonkfun, stonk.fun token data, launches, or fee claims."
---

# Stonkfun

## Purpose
Read-only market/launch data plus prepare-then-sign flows for the Stonkfun
launchpad (`https://www.stonkfun.xyz`). Launching and fee claiming follow a
prepare → browser-sign → submit pattern: the API builds an unsigned
transaction, the user signs it in their own wallet, and the signed bytes are
submitted back. No endpoint signs on anyone's behalf.

## Tooling
`bin/stonk.py` — thin CLI over the public API (no key, no signup):

```
stonk.py GET  /tokens?sort=newest&pageSize=5
stonk.py GET  /tokens/{mint}
stonk.py GET  /tokens/{mint}/fees
stonk.py GET  /pairs?launchable=true
stonk.py GET  /launches?creator={wallet}
stonk.py GET  /stats
stonk.py POST /tokens/{mint}/fees/claim/prepare --data '{"creatorWallet":"..."}'
stonk.py POST /tokens/{mint}/fees/claim/submit  --data '{...signedTransaction...}'
```

NOTE (verified 2026-09-18): `POST /launches/prepare` returns
503 `service_unavailable` — "New launches on this venue are disabled;
launch through LaunchLab instead." The API-prepare launch flow is OFF
(`/stats`: `paidLaunchesEnabled: false`, `launchLabEnabled: true`).
The live launch path is self-built against Raydium LaunchLab — see
"Launching" below. Do not present the API-prepare flow as available.

Responses are the raw JSON the API returns (`{ data: ... }` on success,
`{ error: { code, message } }` on failure).

## Launching
`bin/stonk_launch.py` — launch planner for the self-built LaunchLab path:

```
stonk_launch.py plan --quote-mint <mint> --name "Name" --symbol SYM \
  --tax-bps 0|100|300 \
  --metadata-uri ipfs://... | --metadata-file meta.json | --image art.png [--description "..."]
stonk_launch.py check --mint <mint>   # adoption: launchpad == "launchlab"?
```

`plan` validates the quote (launchable + LaunchLab-ready from `/pairs`),
pulls `/launchlab/pricing`, enforces `raise.raw` sizing, whitelists the tax
tier against `modes.reward.transferFeeBps`, picks the right platform id +
curve-rule account for the mode, pins metadata to IPFS when given a file,
and writes a launch plan JSON to `state/launches/` with every parameter the
`initialize_with_token2022` instruction needs. It signs NOTHING.

The tx itself is built from the plan (Raydium SDK `initializeWithToken2022`,
600k compute units, `mintProgramB` + `platformCurveRuleId` passed as native
SDK params, exact `transferFeeBasePoints` / `maxinumFee` key names for reward
mode). Signing needs creator + fresh mint keypair signatures.

APPROVED 2026-09-18 — option B: scoped local `stonk-launcher` wallet
(`~/.vulcan/wallets/stonk-launcher.json`, scrypt + XSalsa20-Poly1305, 0600;
password never stored, transient per session). Manage with
`bin/stonk_wallet.py` (`create`, `pubkey`).

Execute with `bin/stonk_exec.py` (Python policy wrapper -> Node builder
`bin/launch/stonk_exec.mjs` via stdin pipe; secrets never touch disk/argv):

```
stonk_exec.py --plan state/launches/<name>.plan.json --dry-run   # build + sign locally, no broadcast
stonk_exec.py --plan <plan> --confirm                            # simulate, broadcast, confirm
```

Policy enforced in the wrapper: program id pinned to the LaunchLab program
(`LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj`) — anything else refuses;
per-launch cost cap 0.10 SOL; daily cap 1 SOL (UTC) in
`state/launcher_spend.json`; wallet must hold >= 0.10 SOL; live launch needs
`--confirm` AND the user's chat approval of the exact terms (name, symbol,
quote, tax, metadata URI). No dev buys in v1 — launch only. The mint
authority key is encrypted with the wallet password and stored at
`state/launches/<mint>.mint.json` (0600); every launch is appended to
`state/launches.json`.

After broadcast: `stonk_launch.py check --mint <mint>` until
`launchpad: "launchlab"` (adoption, ~1-2 min). A pool that never adopts
trades on Raydium but the platform records nothing — no fee forwarding.

Metadata policy: every launch pins image + metadata JSON through Pinata/IPFS
and puts `ipfs://<CID>` on-chain. Never example.com / Irys / ephemeral hosts.

## Launch pulse
`bin/stonk_pulse.py` — recurring watch on `/tokens?sort=newest` (cron:
`stonkfun-pulse-6h`, every 6h, goal `stonkfun-launch-pulse`). Finds unseen
mints, ranks newest-first, posts ONE data-only tweet via x-connect (name,
symbol, mcap, graduation %; no advice language). Silent when nothing is new;
failed posts leave mints unmarked so the next run re-surfaces them. State in
`state/stonk_pulse_state.json`.

## Auth
None. The public API is open behind per-IP, per-minute rate limits
(reads: 300/min; `POST /launches/prepare`: 25/min;
`POST /tokens/{mint}/fees/claim/prepare`: 20/min). Honour `Retry-After`
on 429. Read responses are CDN-cached and cost nothing against the limits.

## Operating Rules
1. Never sign anything locally. `prepare` calls return unsigned
   transactions; hand them to the user's browser wallet for signing.
   Launch signing follows the Launching section's A/B decision — no local
   signing under either path without the user's explicit approval.
2. Every launch or fee-claim submit needs the user's fresh, explicit
   approval in chat first. A prepared transaction / plan is not an approval.
3. Launch sizing: `totalFundRaisingB` must be the RAW amount in the quote
   token's decimals — use `raise.raw` from `/launchlab/pricing`, never a
   hardcoded constant.
4. Adoption check: after a self-built LaunchLab launch, confirm it appears
   in `GET /tokens/{mint}` with `launchpad: "launchlab"` before building a
   taxed (reward) variant. A taxed mint that isn't adopted taxes holders
   with no distribution.
5. Fee claims are creator-only: preparing a claim for a token the user did
   not launch returns a transaction they cannot make valid. Don't submit it.
6. `submit` for fee claims is idempotent via `intentId`; a timed-out submit
   is safe to retry, an already-submitted one answers `alreadySubmitted`.
7. Finance boundary: token data here is research/organization only — never
   presented as buy/sell advice.
