# Privy × auto.exchange Integration Patterns

How to combine Privy (wallets, auth, signing) with auto.exchange (agent marketplace). Grounded in https://docs.privy.io/llms-full.txt and https://auto.exchange/docs/llms.txt.

## Pattern 1: Call an auto.exchange agent from a Privy-powered app

Your app already authenticates users with Privy. To call an agent server-side:

```typescript
// Server route (Node.js)
const res = await fetch(`https://api.auto.exchange/agents/${AGENT_ID}/run`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${process.env.AUTO_EXCHANGE_API_KEY}`, // axk_...
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ prompt, session_id: existingOrNew }),
});
const { text, tokens_used, cost } = await res.json();
```

Key points:
- Never expose the `axk_` key client-side. Call from your server.
- Pass `session_id` to continue a multi-turn conversation per user; store the mapping userId → sessionId in your DB.
- `stateless: true` for one-shot calls with no memory.
- auto.exchange also accepts a **Privy JWT** as the authenticated credential on protected endpoints (`Authenticated (API key or Privy JWT)`), so a logged-in user's Privy access token can authorize calls directly — verify the JWT server-side first (see privy-auth.md).

## Pattern 2: Verify a Privy JWT in Node.js (then call auto.exchange)

```typescript
import { PrivyClient } from "@privy-io/server-auth";

const privy = new PrivyClient(process.env.PRIVY_APP_ID!, process.env.PRIVY_APP_SECRET!);

const { userId } = await privy.verifyAuthToken(req.headers.authorization!.replace("Bearer ", ""));
// userId is now trusted — proceed to call the agent as that user
```

Use the verified `userId` to scope `session_id` and to attribute spend per user.

## Pattern 3: Privy server wallet pays for agent runs (MPP)

Instead of a platform API key, a Privy **server wallet** (see privy-wallets.md) can pay per-request via the 402 MPP flow:

1. `POST /agents/:id/run` without auth → 402 challenge with payment details.
2. Server wallet signs a Tempo `splitTransfer` (type-0x76) of USDC on Tempo chain 4217 for the quoted amount.
3. Retry the request with the payment receipt attached.

In practice, prefer the `mppx` client pattern with a wallet you control:

```typescript
import { Mppx, tempo } from "mppx/client";
// fund a dedicated wallet with USDC on Tempo, use its key with mppx
const mppx = Mppx.create({ methods: [tempo({ account })] });
const res = await mppx.fetch(`https://api.auto.exchange/agents/${AGENT_ID}/run`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ prompt }),
});
```

Privy server wallets hold the key in a TEE and sign via policy — combine with Privy **authorization policies** (privy-policies.md) to bound spend: e.g. allow only `splitTransfer` to the auto.exchange payment recipient, with per-day value caps.

## Pattern 4: Create a Privy server wallet and sign a Solana transaction

```typescript
import { PrivyClient } from "@privy-io/server-auth";

const privy = new PrivyClient(APP_ID, APP_SECRET);

// 1. Create a Solana server wallet
const { id: walletId, address } = await privy.walletApi.createWallet({
  chainType: "solana",
});

// 2. Build your Solana transaction (e.g. with @solana/web3.js), then sign
const { signedTransaction } = await privy.walletApi.solana.signTransaction({
  walletId,
  transaction: serializedBase64Tx,
});
// 3. Broadcast yourself (or via your RPC) — Privy signs, you send
```

Use this when your agent needs a Solana identity: the agent (or your backend on its behalf) prepares transactions, Privy signs under policy, your infra broadcasts. Never expose the raw key — it never leaves the TEE.

## Pattern 5: Pay for agents with USDC from a Privy embedded wallet (user-owned)

Flow for a user-facing app where the *user's* Privy embedded wallet pays:

1. User logs in with Privy (email, OAuth, passkey — see privy-auth.md); embedded wallet auto-created.
2. Your backend creates the agent run request and returns the 402 payment details (recipient, amount, chain = Tempo 4217).
3. Client builds a USDC transfer on Tempo and asks the user's embedded wallet to sign (Privy React SDK `useSendTransaction` or `walletApi`).
4. Signed receipt is attached to the retried `/run` call.

Gate this behind a clear confirmation UI showing amount and recipient. For sub-dollar agent calls, consider sponsoring via your own API-key balance and billing the user off-chain instead — fewer signatures, better UX.

## Pattern 6: Agent-to-agent with Privy identity

auto.exchange agents can call each other via `collaborators` + the `call_exchange_agent` tool (sub-agent billed separately at its own price). Combine with Privy:

- Give each of your agents a Privy **server wallet** as its on-chain identity.
- The orchestrator agent passes a Privy-signed authorization (or a scoped JWT) that the sub-agent verifies before acting — see privy-auth.md token verification.
- Track spend per agent via `GET /agents/:id/logs` (tokens, cost, latency per request).

## Pattern 7: SIWS-gated agent access

For premium agents, require the caller to prove control of an on-chain wallet before you
proxy the run with your `axk_` key. Privy supports Sign-In With Solana (SIWS) and Sign-In
With Ethereum (SIWE) for users who already have wallets:

```tsx
import {useLoginWithSiws} from '@privy-io/react-auth';
import {useWallets} from '@privy-io/react-auth/solana';

const {generateSiwsMessage, loginWithSiws} = useLoginWithSiws();
const {wallets} = useWallets();

async function gatePremiumAccess() {
  const wallet = wallets[0];
  if (!wallet) throw new Error("no_wallet");
  // 1. Build the SIWS message for this wallet
  const message = await generateSiwsMessage({address: wallet.address});
  // 2. User signs it in their wallet
  const {signature} = await wallet.signMessage({message});
  // 3. Privy verifies ownership server-side and logs the user in
  await loginWithSiws({message, signature});
}
```

After a successful SIWS login, the app holds a Privy user and JWT. Your backend then
verifies the JWT (Pattern 2), checks that the wallet owns whatever asset, NFT, or role
you gate on, and only then proxies the agent call with the `axk_` key (Pattern 1).
SIWS messages are single-use — generate a fresh message per login so replayed signatures
are rejected.

## Pattern 8: Delegated user signing

Sometimes the agent should prepare an on-chain action but the *user* must approve it —
e.g. the agent builds the USDC transfer that pays the 402 MPP challenge, or stages a
Solana transaction the agent designed. Backend prepares the unsigned transaction,
client asks the user's Privy embedded wallet to sign in-app, backend broadcasts.

```tsx
import {useSendTransaction} from '@privy-io/react-auth/solana';
// (renamed to useSignAndSendTransaction in newer SDK releases)

const {sendTransaction} = useSendTransaction();
// unsignedTx: base64 transaction the agent backend prepared
const {signature} = await sendTransaction({transaction: unsignedTx, connection});
```

For EVM chains the equivalent hook lives in `@privy-io/react-auth` (`useSendTransaction`).
Confirmation-UI requirements — never auto-sign:

- Show the exact amount, recipient address, chain (Tempo 4217 for MPP payments), and expiry.
- One explicit tap-to-confirm per action; a cancel path that aborts cleanly.
- For repeat sub-dollar actions, prefer sponsoring with your API-key balance and billing
  off-chain (Pattern 5) rather than nagging the user with signatures.

## Pattern 9: Per-user spend quotas

`GET /account/usage` shows your aggregate account spend — it does not attribute cost per
user. Track per-user spend in your own ledger so one heavy user cannot drain the account:

```typescript
const {userId} = await privy.verifyAuthToken(token);

// app-owned ledger: quota per user, spend summed per UTC day
const quota = await db.quotas.get(userId);
const spent = await db.spend.sum(userId, todayUtc());
const estimate = estimateCost(prompt); // historical avg output tokens x price_per_1k

if (spent + estimate > quota) {
  return res.status(429).json({error: "quota_exceeded", spent, quota});
}

const run = await fetch(`https://api.auto.exchange/agents/${AGENT_ID}/run`, {
  method: "POST",
  headers: {Authorization: `Bearer ${process.env.AUTO_EXCHANGE_API_KEY}`,
            "Content-Type": "application/json"},
  body: JSON.stringify({prompt, session_id: quota.sessionId ?? "new"}),
}).then(r => r.json());

await db.spend.add(userId, run.tokens_used, run.cost);
```

Tips:

- Persist `session_id` per user so multi-turn conversations continue across requests;
  pass `"new"` to reset a thread deliberately.
- Estimate conservatively: auto.exchange balance pre-checks use the agent's historical
  average output, not worst-case `max_tokens`.
- Enforce the quota *before* calling `/run` — a rejected call costs nothing; an
  over-quota call already spent is gone.

## Pattern 10: Server wallet as agent treasury

When orchestrator agents call collaborators via `call_exchange_agent`, the sub-agent is
billed separately at its own price. Give each of your agents a dedicated Privy server
wallet as its on-chain treasury, and let that wallet pay 402 MPP challenges for the
sub-agent calls it triggers (Pattern 3).

Bound the treasury with Privy authorization policies (see privy-policies.md):

- Allow only MPP `splitTransfer` calls to the auto.exchange payment recipient.
- Restrict to chain Tempo 4217.
- Set per-day value caps and an expiry on the policy.
- Register an owner / authorization key on the wallet so actions require your backend's
  signature — requests to act on the wallet must then be authorized by your server.

Reconcile daily: compare `GET /agents/:id/logs` (per-request tokens, cost, latency for
each of your agents) against the treasury's on-chain outflows. Divergence means a call
bypassed the policy path — investigate before topping up.

## Pattern 11: Full Next.js API route example

Puts Patterns 2 + 9 + 1 together — verify, quota-check, proxy, account:

```typescript
// app/api/agent/run/route.ts
import {PrivyClient} from "@privy-io/server-auth";
import {NextResponse} from "next/server";

const privy = new PrivyClient(
  process.env.PRIVY_APP_ID!,
  process.env.PRIVY_APP_SECRET!
);
const AGENT_ID = process.env.AUTO_EXCHANGE_AGENT_ID!;

export async function POST(req: Request) {
  const token = req.headers.get("authorization")?.replace("Bearer ", "");
  if (!token) return NextResponse.json({error: "missing_auth"}, {status: 401});

  let userId: string;
  try {
    ({userId} = await privy.verifyAuthToken(token));
  } catch {
    return NextResponse.json({error: "invalid_token"}, {status: 401});
  }

  const {prompt, session_id, max_tokens, stateless} = await req.json();
  if (!prompt || typeof prompt !== "string")
    return NextResponse.json({error: "prompt_required"}, {status: 400});

  const allowed = await quotaAllows(userId, prompt); // Pattern 9
  if (!allowed) return NextResponse.json({error: "quota_exceeded"}, {status: 429});

  const res = await fetch(`https://api.auto.exchange/agents/${AGENT_ID}/run`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.AUTO_EXCHANGE_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({prompt, session_id, max_tokens, stateless}),
  });

  if (res.status === 402)
    return NextResponse.json({error: "insufficient_funds"}, {status: 402});
  if (!res.ok)
    return NextResponse.json({error: "agent_error"}, {status: 502});

  const {text, tokens_used, cost} = await res.json();
  await recordSpend(userId, tokens_used, cost); // Pattern 9 ledger
  return NextResponse.json({text, tokens_used, cost});
}
```

Error mapping is deliberate: 401 for your auth failures, 429 for your quota, 402 when
the *platform* balance is empty, 502 when the agent call itself fails — the client can
tell whose problem it is from the status alone.

## Error-handling matrix

| Failure | Privy-side signal | auto.exchange-side signal | Handling |
|---|---|---|---|
| Unauthenticated caller | `verifyAuthToken` throws / no JWT | 401 from `/run` without `axk_` | Reject at your API boundary; never forward unauthenticated calls to a paid endpoint. |
| Expired login | Privy JWT expired | stale `session_id` starts a fresh session | Re-login via Privy; pass `"new"` to start a clean thread intentionally. |
| Payment required | Server-wallet policy denies the tx | 402 MPP challenge | Sign the Tempo `splitTransfer` under policy (Pattern 3) or fund the `axk_` account; retry once with the receipt attached. |
| Rate limited | Too many login attempts | 429 | Back off with jitter; check `/account/usage` for spend anomalies. |
| Provider 5xx | Privy API 5xx | 5xx from `/run` | Retry with a fresh idempotency key — Privy replays cached responses per key on error; never double-charge. |
| Policy denial | Authorization policy rejects the action | (blocked before the call) | Surface to the user; do not retry with the same key; fix the policy (see privy-policies.md). |
| Signature replay | SIWS message already used | — | Generate a fresh SIWS message per login (Pattern 7). |

## Testing checklist

- [ ] Expired, tampered, and wrong-audience JWTs are rejected with 401 *before* any agent call.
- [ ] 402 retry loop: unauthenticated `/run` → challenge → policy-bounded sign → retried run succeeds; the receipt is attached exactly once.
- [ ] Quota: an over-quota user gets your 429 and zero tokens are consumed on auto.exchange.
- [ ] Session continuity: two runs with the same `session_id` reference earlier turns; `"new"` resets.
- [ ] Policy denial: server wallet asked to sign a disallowed recipient → denied, no retry, alert raised.
- [ ] SIWS: a replayed signature is rejected; each login uses a fresh message.
- [ ] Delegated signing UX: the confirmation screen shows amount, recipient, and chain; cancel aborts with no partial state.

## Cost notes per pattern

- **P1/P2 (server proxy + JWT verify):** one `/run` call per request; cost = output tokens × `price_per_1k`. JWT verification is a single Privy API call — no token cost.
- **P3 (server-wallet MPP):** adds one Tempo signature + gas on chain 4217 per run; bound by policy caps.
- **P4 (Solana sign via TEE):** one Privy signing call per transaction; you pay Solana network fees on broadcast yourself.
- **P5 (user pays):** zero `axk_` spend; the user's wallet pays one Tempo transaction fee per run.
- **P6 (collaborators):** sub-agent billed at its own `price_per_1k`; reconcile with `GET /agents/:id/logs`.
- **P7 (SIWS gate):** one signature per login; no per-run extra cost.
- **P8 (delegated signing):** one wallet signature per approved action — design for few signatures (one confirmation screen per intent).
- **P9 (quotas):** adds one ledger read per call; cache hot users in memory.
- **P10 (treasury):** same as P3 plus policy-management overhead; reconcile daily.
- **P11 (Next.js route):** same as P1 plus one quota lookup; keep the route warm.

## Security checklist

- `axk_` keys and `PRIVY_APP_SECRET` live server-side only, never in client bundles.
- Verify Privy JWTs on every request; check expiry and audience.
- Bound server-wallet policies: allowed chains (Tempo 4217 for MPP), allowed recipients, value caps, expiry.
- Attribute auto.exchange spend per user (`/account/usage`, per-agent logs) and enforce your own quotas before calling.
- For code-review style agents, request machine JSON output (`file, line, severity, issue, old, new, reason, impact`) so results are actionable downstream.
