---
name: "privy-device-auth"
description: "Privy OAuth 2.0 Device Authorization Grant for Musebook: approve once in the browser at https://musebook.trade/authorize, then sign with the user's Privy embedded Solana wallets headlessly. Covers login, token refresh/rotation, HPKE wallet authentication, canonical request signatures, message/tx signing (sign only, never broadcast), grant audit/revocation, and logout."
---

# Privy Device Auth

Agent-side OAuth 2.0 Device Authorization Grant for Musebook's Privy app.

**One-time browser approval, then headless.** The user visits
`https://musebook.trade/authorize`, enters the code shown by `login`, and
approves. From then on the agent holds only short-lived tokens and signs
with the user's Privy embedded Solana wallets. **No Privy app secret is
required or used anywhere** — device flows are public-client by design.

- Privy app id: `cm7tbyvvy01w2144yss67bjm0`
- API base: `https://auth.privy.io`
- Verification page: `https://musebook.trade/authorize`
  (added in the Privy dashboard, with "CLI and agent access" enabled)

## Quick start

```bash
cd ~/workspace/skills/privy-device-auth

# 1. Log in (device flow). Needs cryptography + keyring once:
python3 -m venv ~/.venvs/privy-device-auth
~/.venvs/privy-device-auth/bin/pip install cryptography keyring
# or use the bundled venv: ./.venv/bin/python

./bin/privy_device.py login
# → visit https://musebook.trade/authorize, enter the shown code, approve

./bin/privy_device.py status     # session + token expiry, no secrets printed
./bin/privy_device.py wallets    # Privy wallets on this grant

./bin/privy_device.py sign-message --wallet <wallet_id> --message "hello"
./bin/privy_device.py sign-tx --wallet <wallet_id> --tx <base64_tx>

./bin/privy_device.py revoke                 # list active authorizations
./bin/privy_device.py revoke --grant-id <id> # revoke one (asks for a browser user token)
./bin/privy_device.py logout                 # delete the stored session
```

`--wallet` takes the **wallet id**, not the address (see `wallets` output).

## Security model

- **Never printed or logged:** access tokens, refresh tokens, device codes,
  decrypted wallet authorization keys. `status` shows presence/expiry only;
  errors carry HTTP status + Privy error code, never response bodies.
- **Token storage:** OS keychain via optional `keyring` when available
  (macOS Keychain / Secret Service / Windows Credential Manager). Otherwise
  an AES-256-GCM file at `~/.config/privy-device-auth/session.enc` (dir
  `0700`, file `0600`, atomic writes), with the key derived machine-bound
  via HKDF-SHA256 over the Linux machine id (hostname/home fallback) —
  **and a loud warning every time**, because this is weaker than a keychain.
- **The decrypted wallet authorization key is memory-only.** It is fetched
  from `wallets/authenticate` via HPKE and cached in-process until its
  `expires_at`; it is never written to disk.
- **Wallet membership is enforced:** every signing call verifies the wallet
  id against the wallet list Privy returned for the authenticated grant and
  requires `chain_type == "solana"`. Anything else is refused.
- **`sign-tx` signs only.** The skill has no transaction-submission path by
  design; the signed base64 transaction is printed for the operator to
  submit through their own Solana RPC only with explicit approval.
- **The device code is kept in memory only** for the duration of `login`.

## Token lifetimes

| Token | Lifetime | Behavior |
|---|---|---|
| Device / user code | 10 min | Poll loop: `authorization_pending` → keep waiting; `slow_down` → wait 5s longer; `expired_token` → restart `login`; `access_denied` → stop. |
| Access token | 15 min | Refreshed proactively 60s before expiry, and retried **once** after a 401. |
| Refresh token | 30 days | **Rotated on every use.** The replacement is persisted atomically on each refresh; losing it silently loses access. |

## Grant audit / revocation

`revoke` is a **browser-token operation**: it needs a browser-derived Privy
**user access token**, not the stored device-grant token. It reads
`PRIVY_USER_ACCESS_TOKEN` if set, otherwise asks on a non-echoing prompt.
The token is never stored or printed. Without `--grant-id` it lists active
authorizations; with `--grant-id` it asks for explicit `YES` confirmation
before deleting.

Revocation invalidates refresh tokens immediately; an access JWT minted
before revocation can remain valid for up to ~15 minutes.

## How it works (protocol summary)

All facts below were verified 2026-09-19 against Privy's docs and its
official `@privy-io/agent-wallet-cli` v0.3.6 / Go SDK, plus a real
`device_authorization` probe:

1. `POST /api/oauth/v2/device_authorization` → `{device_code, user_code,
   verification_uri(_complete), expires_in, interval}`. Every call sends
   `privy-app-id: cm7tbyvvy01w2144yss67bjm0`.
2. `POST /api/oauth/v2/token` with
   `grant_type: "urn:ietf:params:oauth:grant-type:device_code"` (+ device_code
   while polling; `grant_type: "refresh_token"` + refresh_token for refresh).
3. `POST /api/oauth/v2/wallets/authenticate` (`Authorization: Bearer <access>`,
   `privy-grant-type: device_code`) with
   `{"encryption_type": "HPKE", "recipient_public_key": <base64 DER SPKI of an
   ephemeral P-256 key>}`. Privy returns `encrypted_authorization_key`
   (`encapsulated_key` + `ciphertext`), `expires_at`, and `wallets`.
   HPKE suite: **P-256 KEM / HKDF-SHA256 / ChaCha20-Poly1305**, no info/AAD —
   exactly what the official CLI uses. Decrypt `enc || ct` to get the P-256
   authorization private key (PEM or base64 PKCS8).
4. `POST /api/oauth/v2/wallets/{wallet_id}/rpc` with
   `privy-grant-type: device_code` + `Authorization: Bearer <access>` +
   `privy-authorization-signature: base64(DER(ECDSA_P256(
   SHA256(JCS({version:1, method:"POST", url, body,
   headers:{"privy-app-id":...}})))))`. A body that canonicalizes to `{}`
   is signed as `""`. The signature covers `privy-app-id` only (the grant
   type rides along unsigned, matching the official CLI).
5. RPC methods used: `signMessage` (`params: {message: base64(utf8), encoding:
   "base64"}`) and `signTransaction` (`params: {transaction: base64,
   encoding: "base64"}`). `signAndSendTransaction` is never called.
6. `GET /api/oauth/v2/grants` / `DELETE /api/oauth/v2/grants/{id}` for audit.

## Tests

```bash
./bin/privy_device.py selftest          # 40 checks: JCS vector, sig verify,
                                        # HPKE roundtrip, poll table, storage
                                        # round-trip + 0600 + encryption,
                                        # refresh rotation, redaction, parsing
~/.venvs/privy-device-auth/bin/python tests/test_privy_device.py  # 11 checks with mocked HTTP:
                                        # invalid base64 rejected pre-network,
                                        # wallet ownership/chain-type refusal,
                                        # 401 → refresh → retry exactly once,
                                        # no broadcast path, RFC grant URN
```

Live end-to-end (the actual browser approval at
`https://musebook.trade/authorize`) still needs a human in a browser and was
deliberately not run here.
