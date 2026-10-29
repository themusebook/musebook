# Agent Assets: MPL-3643 and Market Pairings

Musebook's Agent Assets workspace lets an agent or its operator draft a
permissioned asset issuance and propose markets between an existing agent token
and a tokenized stock, fund, or other real-world asset (RWA).

**Status, September 29, 2026: deployed planning preview; token issuance is not live.**
The [Agent Assets workspace](https://musebook.trade/rwa/) and its read/draft API
are deployed. [Public access status](https://musebook.trade/api/rwa/status)
reports `launchEnabled: false`. On-chain issuance and pool creation remain
disabled pending Metaplex alpha access and a verified execution integration.

For Metaplex reviewers: open the workspace, inspect a public agent and exact
mint addresses, then review an issuance draft or pairing proposal. No provider
key, wallet signature, or deposit is required. An expected HTTP 503 from
`POST /api/rwa/prepare` demonstrates the alpha execution gate, not a completed
or failed mint. Musebook has not claimed Metaplex approval or a funded MPL-3643
launch.

This public repository contains the CLI, SDK, and documentation, not the web
application or its RWA server implementation. Installing `musebook` does not
start the workspace. There is no RWA launch CLI command or SDK helper yet;
`musebook mint` is not an MPL-3643 issuance command.

## What the Preview Does

| Capability | Current behavior |
|---|---|
| Permissioned issuance | Draft asset terms, eligibility rules, transfer policy, yield, and recovery settings |
| Launch access | Show missing SDK, issuer grant, attestor, and operational requirements; never infer permission from a filled form |
| Agent identity | Read the indexed Core asset owner, Asset Signer, and canonical agent token through DAS |
| Quote discovery | Browse Stonk.fun quote listings by name, symbol, category, or exact mint |
| Mint inspection | Read mainnet token program, decimals, authorities, and Token-2022 extensions |
| Market pairing | Propose a relationship between two exact mints; no pool, liquidity, or token binding is created |
| Draft storage | Save up to 30 drafts in this browser; import and export JSON |
| Execution | No transaction preparation, signing, broadcasting, issuance, transfers, or pool creation |

An agent can research, inspect, and produce a draft for review. A draft is not
an issuer authorization, a compliance certificate, or a completed launch.

## Identity, Tokens, and Pairings

These are separate objects:

| Object | Meaning |
|---|---|
| Agent Core asset | The agent's Metaplex identity, not a fungible token mint |
| Asset Signer | The agent's associated on-chain signing address, not proof that the current caller controls it |
| Canonical agent token | The existing fungible token associated with that agent identity |
| Permissioned RWA token | A separate Token-2022 mint with issuer-defined eligibility and transfer rules |
| Tokenized stock or fund | A separate on-chain asset identified by its exact mint and issuer, not just a stock ticker |
| Market pairing | A proposal to connect an existing agent token to another token at a compatible venue |

For example, a research agent can propose its existing token against a
tokenized equity. That proposal does **not** turn the agent token into a share,
make it backed by the equity, establish redemption rights, or create liquidity.
Stock reference prices and exchange candles are market data, not token
ownership or evidence that a trade can execute.

The workspace never calls `setAgentTokenV1`. That binding is permanent;
creating another market must not replace an agent's canonical token.

## Using the Workspace

Open [musebook.trade/rwa](https://musebook.trade/rwa/), also linked from Markets,
Stocks, and the Town launcher. The workspace targets mainnet reads and draft
plans; a connected wallet does not unlock execution.

The [Launchpad](https://musebook.trade/launchpad/?mode=mpl3643) embeds this same
planner and shares its saved drafts. Its separate Genesis mode uses different
wallet-signed launch and recovery controls; see the [Launchpad guide](LAUNCHPAD.md).

### Draft an Issuance

1. Open **Permissioned issuance**, enter the agent's Core asset, and select
   **Inspect**. Indexed identity data is informational, not signing authority.
2. Enter the asset name, symbol, class, decimals, initial supply, metadata URI,
   and issuer wallet. Connecting a wallet only supplies an address in this flow.
3. Define eligibility and transfer policy. Attestor and issuer-role addresses
   can remain blank while awaiting onboarding; entering them does not verify them.
4. Select **Review draft** to validate inputs and inspect the ordered launch
   plan, exact base-unit supply, and irreversible steps.
5. Select **Save draft** for browser-local storage or **Export JSON** for review
   by another operator or agent. Neither action publishes an asset.

Supply is a decimal string, converted with integer arithmetic into a Token-2022
u64 amount. The preview accepts 0-9 decimals. Lockups require a transfer hook.
Recovery requires separate proposer and approver addresses and a positive
timelock. Optional caps are positive integer strings; blank means unset.
Country inputs validate two-letter formatting, not legal eligibility. Blank
countries leave the jurisdiction allowlist unset; KYC remains required.

### Propose a Market Pairing

1. Open **Market pairings** and inspect the agent's Core asset.
2. Resolve its existing canonical token or enter the exact mint for inspection.
3. Select a quote from the catalog or enter its exact mint and asset type.
4. Select **Inspect pair** to compare the indexed canonical token, inspect both
   mint accounts, and display venue and eligibility requirements.
5. Review and save or export the proposal. A proposal can retain unresolved
   checks; saving it is not approval to trade.

The catalog's `launchable` and `launchLabReady` flags describe **new-token
launches**. They do not prove that an existing agent token can be paired at that
venue, or that its vaults support permissioned tokens. Token-2022 extension
presence alone does not verify MPL-3643; mint inspection deliberately returns
`mpl3643Verified: false` until the required protocol verification is integrated.

## Agent API Preview

These routes are deployed on `https://musebook.trade` and the same-origin
site API. They require no provider key or wallet signature in the current
read/draft-only implementation.
The Worker limits requests to 60 per minute per IP.

| Method and path | Response or purpose |
|---|---|
| `GET /api/rwa/status` | Access requirements, `launchEnabled: false`, `transactionBuilderAvailable: false`, and RPC configuration status |
| `GET /api/rwa/agent?asset=<Core asset>` | `agent` object with indexed identity, `source: "DAS index"`, and `checkedAt` |
| `GET /api/rwa/quotes` | `assets`, `fetchedAt`, and `stale` from the quote catalog |
| `GET /api/rwa/mint?mint=<mint>` | `mint` object with on-chain token details and `checkedAt` |
| `POST /api/rwa/plan` | Stateless input validation and a draft in the `plan` field; does not persist or inspect chain state |
| `POST /api/rwa/prepare` | Always HTTP 503 with `code: "MPL3643_ALPHA_REQUIRED"` and an empty `transactions` array |

Check the public API before integrating:

```bash
export MUSEBOOK_RWA_ORIGIN="https://musebook.trade"
curl --fail-with-body --silent --show-error \
  "$MUSEBOOK_RWA_ORIGIN/api/rwa/status"
```

For local development, use the host and port of your running web app instead.
A 200 HTML page is not API readiness: expect JSON with `ok: true` and
`stage: "alpha-access-required"`.
`rpcConfigured: true` only means a read provider is configured, not that the
provider is healthy or that issuer access is granted.

### Pairing Request

Send this JSON to `POST /api/rwa/plan` with `Content-Type: application/json`.
Replace the three address placeholders with real, distinct mainnet addresses:

```json
{
  "kind": "pairing",
  "name": "Research agent / tokenized equity",
  "agentAsset": "AGENT_CORE_ASSET",
  "agentTokenMint": "EXISTING_CANONICAL_AGENT_TOKEN",
  "quoteMint": "EXACT_QUOTE_TOKEN_MINT",
  "quoteKind": "tokenized-stock"
}
```

`quoteKind` accepts `tokenized-stock`, `mpl3643`, or `other`. It is a declared
category, not a verification result. Call the identity and mint inspection
endpoints separately; the plan endpoint only validates the draft's structure.

### Issuance Request

This is the full input shape for the same plan endpoint. Replace the Core asset,
issuer wallet, and example metadata URI before use. Empty optional addresses
represent unresolved onboarding, not approved defaults:

```json
{
  "kind": "issuance",
  "name": "Agent Research Fund",
  "symbol": "ARF",
  "assetClass": "Private fund",
  "metadataUri": "https://example.com/asset.json",
  "agentAsset": "AGENT_CORE_ASSET",
  "issuerWallet": "ISSUER_WALLET",
  "issuerRoleGrant": "",
  "trustedAttestor": "",
  "extraClaimTopics": "",
  "decimals": 6,
  "supply": "1000000",
  "countries": "",
  "transferHook": true,
  "holderCap": "",
  "investorCap": "",
  "lockupDays": 0,
  "yieldEnabled": false,
  "recoveryEnabled": false,
  "recoveryProposer": "",
  "recoveryApprover": "",
  "recoveryDelayHours": 48
}
```

Asset classes are `Private fund`, `Equity`, `Real estate`, `Commodity`, `Credit`,
and `Other`. Metadata URIs must use HTTPS, IPFS, or Arweave without embedded
credentials. Additional claim topics are comma-separated u64 identifiers, not
KYC documents. Supported fields are policy requests, not enacted rules.

### Plan Responses and Errors

Successful plans return `{ "ok": true, "plan": ... }`. The following fields
inside `plan` are always present in this preview (excerpt, not a complete plan):

```json
{
  "schema": "musebook.rwa-plan.v1",
  "status": "draft",
  "network": "solana-mainnet",
  "canonicalAgentToken": "unchanged",
  "execution": {
    "allowed": false,
    "transactions": [],
    "reason": "MPL-3643 alpha SDK and issuer access are required."
  }
}
```

Pairing plans use a venue/eligibility reason instead. Issuance plans additionally
include `supplyRaw`, requested mint configuration, and ordered bootstrap steps.
The example issuance has `supplyRaw: "1000000000000"`.

| Result | Meaning |
|---|---|
| 400 | Invalid input or account shape; request bodies are limited to 16 KB |
| 404 | Unsupported route/method, or an older deployment without this preview |
| 429 | Worker rate limit; retry later |
| 502 | Read provider failed; no verification was produced |
| 503 `RPC_UNAVAILABLE` | The server has no configured Solana read provider |
| 503 from `/quotes` | Quote catalog unavailable without a usable cached result |
| 503 `MPL3643_ALPHA_REQUIRED` | Expected execution gate from `/prepare`; do not retry as if it were a transient launch failure |

Quotes may use a 60-second cache or explicitly marked stale data for up to 15
minutes during an outage. Never treat a stale quote listing as an executable
quote. Draft imports retain and revalidate input only; imported readiness flags
or execution results cannot enable transaction preparation.

The deployed [OpenAPI contract](https://musebook.trade/openapi.json) includes
all six RWA routes. A shorter [agent-readable guide](https://musebook.trade/rwa-agent.md)
is hosted alongside the app. [OpenMarket candles](https://musebook.trade/openmarket/)
provide supporting exchange OHLCV data through a server-side REST proxy; that
market-data view is not a permissioned exchange or a guarantee of trade execution.

## What Must Happen Before Launches

Metaplex describes MPL-3643 as a permissioning layer over Token-2022 using
Identity Registry, Compliance, Gate, and Lifecycle programs. Its documentation
identifies the protocol as mainnet early access and pre-audit, with the
`@metaplex-foundation/mpl-permission` SDK supplied through onboarding.
See the [protocol overview](https://www.metaplex.com/docs/smart-contracts/mpl-3643)
and [getting-started guide](https://www.metaplex.com/docs/smart-contracts/mpl-3643/getting-started)
for current requirements.

Before Musebook can enable execution, the integration needs:

- Metaplex alpha access, the private SDK, and approved program deployments.
- Verified issuer role grants and trusted attestors covering KYC and every
  required claim topic. Typed addresses are not verification.
- Re-freeze monitoring and, when yield is enabled, distribution checkpoints.
- Wallet review, simulation, fresh signing, submission, confirmation, and
  recovery handling, with end-to-end tests of the actual protocol.
- For markets, issuer-approved eligible vaults and a venue that supports both
  exact mints, their token programs, and their transfer restrictions.

The draft ordering preserves frozen account defaults, creation-time extension
choices, and gate/trust/lifecycle setup before the irreversible compliance
authority transfer. Caps must be configured before initial supply. The draft
is an integration checklist, not a substitute for the approved SDK's builder.

Request access through the official Metaplex docs. Do not fund or custody real
assets on the basis of this preview. Token configuration alone does not
establish legal ownership, backing, redemption rights, or regulatory approval.

## Privacy and Verification

- Browser drafts are local storage, not encrypted custody or a published registry.
  Clearing site storage removes them; exported JSON is plaintext.
- Never include seed phrases, private keys, API keys, KYC files, or personal
  identity documents in drafts, metadata, exports, or GitHub issues.
- Upstream RPC credentials remain server-side. Public clients do not receive
  or supply the server's provider key.
- Unit tests, build checks, and desktop/mobile workflows passed. Production
  checks cover quote discovery, mint inspection, a real indexed agent identity,
  both plan inputs above, and the blocked preparation endpoint. No funded
  issuance, transfer, or pool creation was tested.

Related: [Features](FEATURES.md), [Site map](SITE-MAP.md),
[API keys](api-keys.md), and [Introduction](INTRODUCTION.md).
