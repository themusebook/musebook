# Privy Authentication

Login methods, access/refresh/identity tokens, server-side JWT verification, sessions, logout, and custom auth providers. Source: https://docs.privy.io/llms-full.txt (verified 2026-09-22).

## Login methods

Configure login methods in the Privy Dashboard under **Authentication**. Every client SDK requires at least one enabled login method. Available methods include:

- **Email** — one-time password (OTP) sent to the user's inbox; OTP valid for 10 minutes. Optional `+` alias handling configurable in the dashboard.
- **SMS** — OTP to a phone number (US/Canada included on all plans; additional per-SMS charges may apply on other plans).
- **Social OAuth** — Google, Apple, X/Twitter, Discord, GitHub, LinkedIn, and additional OAuth providers.
- **Passkeys** — WebAuthn-based login; also recommended as an MFA factor.
- **Wallets** — sign-in with an existing EVM or Solana wallet (SIWE/SIWS message signing).
- **Farcaster / Lens** — social-protocol identities as login methods.
- **WhatsApp** — OTP over WhatsApp where supported.
- **Custom auth** — bring your own authentication provider and map it into Privy users.

Privy recommends enabling MFA (passkey or authenticator app) because account access at a delegated provider is wallet access: if the provider account is compromised or deleted, wallet access may be lost permanently.

### React login quickstart

```tsx
import { usePrivy } from "@privy-io/react-auth";

function LoginButton() {
  const { ready, authenticated, login, logout, user } = usePrivy();
  if (!ready) return null;
  return authenticated
    ? <button onClick={logout}>Log out ({user?.email?.address})</button>
    : <button onClick={login}>Log in</button>;
}
```

`login()` opens Privy's auth UI with your configured methods. `logout()` ends the session client-side.

## Token model

Privy issues three token types on authentication:

| Token | Format | Lifetime | Purpose |
|-------|--------|----------|---------|
| Access token | ES256 JWT | 1 hour (configurable in Dashboard > User management > Authentication > Advanced) | Prove authentication on backend calls |
| Refresh token | Opaque string | 30 days (configurable) | Renew access tokens without re-login; SDK-managed, not directly accessible |
| Identity token | JWT | Short-lived | Carry user data claims for identity use cases |

### Access token claims

Privy access tokens are ES256-signed JWTs with these claims:

| Claim | Meaning |
|-------|---------|
| `sid` | Current session ID |
| `sub` | User's Privy DID (use as the stable user identifier) |
| `iss` | Always `privy.io` |
| `aud` | Your Privy app ID |
| `iat` | Issued-at timestamp |
| `exp` | Expiry timestamp (~1h after issue) |

## Getting the access token client-side

In React, `getAccessToken` from the `usePrivy` hook returns the current token and **automatically refreshes it** if expired or near expiry:

```tsx
const { getAccessToken } = usePrivy();

const res = await fetch("/api/me", {
  headers: { Authorization: `Bearer ${await getAccessToken()}` },
});
```

Outside React context, import it directly (requires `PrivyProvider` to have rendered):

```ts
import { getAccessToken } from "@privy-io/react-auth";
const token = await getAccessToken();
```

React Native: use `getAccessToken` from the `PrivyClient` instance created via `createPrivyClient({ appId })`.

## Verifying the access token (server-side)

Always verify the token on your backend before trusting the request. Verify against Privy's verification key for your app (copy it from Dashboard > Configuration > App settings to avoid a key-fetch round trip).

### Using the Privy Node SDK (recommended)

```ts
import { PrivyClient } from "@privy-io/node";

const privy = new PrivyClient({
  appId: process.env.PRIVY_APP_ID!,
  appSecret: process.env.PRIVY_APP_SECRET!,
  // Optional: paste the verification key from the dashboard to skip the key-fetch call
  // jwtVerificationKey: process.env.PRIVY_JWT_VERIFICATION_KEY!,
});

try {
  const claims = await privy.utils().auth().verifyAccessToken({
    access_token: tokenFromHeader,
  });
  // claims: { appId, userId (Privy DID), issuer: 'privy.io',
  //           issuedAt, expiration, sessionId }
  const userId = claims.userId; // trusted — scope sessions/quotas to this
} catch {
  // Expired, wrong app ID, or malformed — do NOT authorize the request
}
```

`verifyAccessToken` throws on any invalid token: expired, wrong audience, bad signature. Treat a throw as "unauthenticated".

### Using `jose` (no Privy SDK)

```ts
import * as jose from "jose";

const verificationKey = await jose.importSPKI(
  process.env.PRIVY_JWT_VERIFICATION_KEY!, // SPKI PEM from the dashboard
  "ES256"
);

try {
  const { payload } = await jose.jwtVerify(tokenFromHeader, verificationKey, {
    issuer: "privy.io",
    audience: process.env.PRIVY_APP_ID!,
  });
  const userId = payload.sub; // Privy DID
} catch {
  // unauthenticated
}
```

### Using `jsonwebtoken`

```ts
import jwt from "jsonwebtoken";

const verificationKey = process.env.PRIVY_JWT_VERIFICATION_KEY!.replace(/\\n/g, "\n");

try {
  const decoded = jwt.verify(tokenFromHeader, verificationKey, {
    issuer: "privy.io",
    audience: process.env.PRIVY_APP_ID!,
  }) as { sub: string };
  const userId = decoded.sub;
} catch {
  // unauthenticated
}
```

### SDK migration note

Older code may use `@privy-io/server-auth` with `new PrivyClient(appId, appSecret)` and `privy.verifyAuthToken(token)`. The current package is `@privy-io/node` (config object, resource interfaces, `verifyAccessToken`). New integrations should use `@privy-io/node`; legacy `verifyAuthToken` call sites still work but are superseded.

## Sessions

- A successful login creates a session; the access token's `sid` claim identifies it.
- Refresh tokens (30-day default, opaque, SDK-managed) silently renew access tokens via `getAccessToken()` — users stay logged in across visits without re-authenticating.
- Session persistence behavior is configurable (see "Customizing session persistence" in the docs).
- `logout()` clears the local session. For stricter server-side enforcement, verify the token on every request and check `exp`; short access-token lifetimes bound replay windows.
- Authentication state in React: `usePrivy()` exposes `ready`, `authenticated`, and `user`.

## Identity tokens

Separate from access tokens: identity tokens carry user data claims for identity use cases (see `user-management/users/identity-tokens` in the docs). Use access tokens for "is this request authenticated", identity tokens for "what do I know about this user".

## Custom authentication providers

You can integrate your own auth provider with Privy (dashboard: Authentication > custom provider). Privy maps your provider's identity into a Privy user/DID, after which the standard token model (access/refresh/identity) applies. Useful when migrating an existing user base without forcing re-login.

## MFA

Multi-factor authentication (passkey or authenticator app) can be required per app. Given the account-access-is-wallet-access warning above, require MFA for any app where embedded wallets hold meaningful value.

## Logout

```tsx
const { logout } = usePrivy();
await logout();
```

Clears tokens and session client-side. Backends that cached a token should rely on its short expiry; do not accept tokens past `exp`.

## Common verification failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Throw on every token | Wrong verification key or wrong `aud` | Paste the key from Dashboard > Configuration > App settings; set `audience` to your exact app ID |
| Intermittent failures | Token expired mid-request | Call `getAccessToken()` fresh per request; it auto-refreshes |
| Valid token, wrong user | Trusted client-supplied `sub` | Always use the `sub` from the *verified* claims, never from the request body |
| Works locally, fails in prod | Env var with literal `\n` in PEM key | Apply the `.replace(/\\n/g, "\n")` normalization shown above |
| `issuer` mismatch | Token from a different app or environment | Ensure frontend and backend share the same Privy app ID |

## Security checklist

- Verify the access token on **every** backend request; check `iss === 'privy.io'`, `aud === your app ID`, and expiry.
- Never trust a `sub`/DID that arrived without verification.
- Keep `PRIVY_APP_SECRET` and the verification key server-side; the app ID alone is public.
- Prefer the dashboard-pasted verification key to avoid a key-fetch on every cold start.
- Shorten access-token lifetime in the dashboard if your threat model needs tighter replay bounds.
- Require MFA where wallets hold value.
- When gating paid resources (e.g. auto.exchange agent calls), bind spend quotas and session IDs to the verified `sub`, not to client-supplied identifiers. See privy-x-ax-patterns.md Pattern 9.
