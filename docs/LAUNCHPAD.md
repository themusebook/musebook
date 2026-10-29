# Launchpad

[Open the launchpad](https://musebook.trade/launchpad/).
The workspace separates permissioned-asset planning, browser-signed Genesis
agent-token launches, Stonk.fun paired-token launches, standalone fungible tokens, Metaplex discovery, and existing
SPL Token Metadata asset management.

## Paired Tokens

The default workspace uses searchable quote-asset tiles and a launch summary.
Choose a live eligible pair, enter token metadata, prepare a fresh transaction,
review the exact mint and costs, and approve in your wallet. Pending signatures
survive reloads and must be reconciled before creating a replacement. This form
supports standard LaunchLab tokens, not permissioned MPL-3643 issuance or reward
baskets. Read the [market and launch guide](MARKET_LAUNCH_DESK.md) for configuration,
recovery, provider limits and the distinction between confirmation and adoption.

## Manage Existing Assets

Open [Manage assets](https://musebook.trade/launchpad?mode=manage) to load a mint and,
for burns or locks, an explicit token account. Updates require the current update
authority; creator verification requires that creator's signature; locks require
an already approved token delegate; burns require the token-account owner.

The workspace supports partial metadata updates, creators, collection set/clear,
pNFT rule-set set/clear, primary-sale marking, authority changes, permanent
immutability, creator verify/unverify, delegated lock/unlock and owner burns.
Omitted metadata fields preserve existing values; empty strings, zero and null do
not mean unchanged. Other verified creators cannot be forged or removed.

`GET /api/metaplex/metadata/{mint}?network=mainnet|devnet&token=<optional-account>`
reads confirmed chain state. `POST /api/metaplex/metadata/{mint}/prepare` takes
`{wallet,network,action,changes?,token?,amount?}` and returns an unsigned SDK
transaction with its original blockhash and fetched state. The server does not
simulate, sign or broadcast. The browser independently rebuilds, checks, simulates
and reviews it, then requests a wallet signature and retains a recovery receipt.

Burns, immutable metadata and authority changes require exact mint confirmation.
Burns are permanent; rent refunds vary and the mint account remains open. Locking
can prevent owner transfer, burn and delegate revocation. Never repeat an action
after an uncertain send until its saved receipt has been checked.

This does not manage Core, Token-2022 or MPL-3643. Delegated metadata updates,
delegate grants, collection verification, printed-edition mint/burn operations
and custom authorization-rule payloads are not implemented here. Unsupported
conditions fail closed. See the [agentic layer guide](AGENTIC-LAYER.md) and
[OpenAPI](../openapi.json) for exact inputs and remaining acceptance gates.
These are different flows with different readiness gates.

| Workspace | Direct Link | Execution |
| --- | --- | --- |
| Paired tokens | [/launchpad?mode=paired](https://musebook.trade/launchpad?mode=paired) | Browser-signed Stonk.fun LaunchLab; explicit review and recovery |
| Permissioned assets | [/launchpad?mode=mpl3643](https://musebook.trade/launchpad?mode=mpl3643) | Draft-only; alpha access required |
| Agent tokens | [/launchpad?mode=genesis](https://musebook.trade/launchpad?mode=genesis) | Owner-wallet Genesis launch |
| Create token | [/launchpad?mode=fungible](https://musebook.trade/launchpad?mode=fungible) | Atomic SPL + Token Metadata creation |
| Explore | [/launchpad?mode=discover](https://musebook.trade/launchpad?mode=discover) | Read-only launches and DAS |
| Creator rewards | [/claim](https://musebook.trade/claim) | Wallet-reviewed fee claims |

## Creator Rewards

[/claim](https://musebook.trade/claim) opens the creator-reward workspace; Town
registration is not required. Agent onboarding remains at
[/claim?mode=onboarding](https://musebook.trade/claim?mode=onboarding).

| Provider | Covered Rewards | Network |
| --- | --- | --- |
| Metaplex | Genesis bonding-curve creator fees and graduated Raydium CPMM buckets | Mainnet or devnet |
| Pump | Curve/AMM creator fees, cashback and shared creator-fee operations | Mainnet |
| Raydium | Existing LaunchLab creator vault and CPMM creator-fee tools | Mainnet |

Metaplex scans all eligible buckets for the **configured creator fee recipient**,
not every token the connected wallet holds. The recipient can be a different
wallet or an agent Asset Signer PDA. The connected wallet pays network fees and
any account rent; it does not become the reward recipient. Claiming into an
agent PDA does not withdraw funds from the agent.
Agent-associated Genesis launches default to the agent PDA when no creator-fee
override is configured. The confirmed agent-launch receipt opens `/claim` with
the agent and network prefilled. The Agent fee recipient control derives the
Asset Signer with the official Core SDK; derivation is not an ownership check.

1. Connect an installed Solana wallet or choose the site wallet.
2. Choose the provider and network. Metaplex defaults to mainnet. Check the
   recipient address against the launch's creator-fee configuration.
3. Check rewards, then review claims. The app inspects the unsigned instructions,
   verifies recipient/payer accounts, simulates and shows the buckets and
   estimated network fees. Additional account rent may apply; actual rewards
   depend on on-chain balances at execution time.
4. Explicitly sign each transaction. Claims keep the blockhash supplied by the
   Metaplex API, are re-simulated before signing and sent sequentially with
   preflight. Unexpected transfers or changed transaction messages are rejected.
5. Every expected signature is saved **before** broadcasting. A lost response,
   rejected later signature or reload retains the partial receipt. Check claim
   status without another signature or broadcast. Recovery matches each on-chain
   transaction message to the saved receipt.
6. Close a receipt only after submitted transactions are confirmed, failed, or
   provably expired past finalized block height. Unsubmitted buckets remain
   unclaimed; build a fresh review after reconciling the receipt. Do not clear
   site storage while a signature is unresolved.

The Genesis receipt safeguards also apply to the Town's Genesis rewards panel.
Only public addresses, message hashes, blockhashes and signatures are stored,
never wallet keys or signed transaction bytes. Pump retains its separate pending
journal. Raydium's existing tools remain separate, not a combined claim batch.

### Reward API

| Method | Path | Input |
| --- | --- | --- |
| GET | `/api/genesis/rewards/status` | `wallet`, optional `payer`, `network` |
| POST | `/api/genesis/rewards/claim` | JSON `wallet`, optional `payer`, `network` |

Networks are `solana-mainnet` (default) and `solana-devnet`; `mainnet` / `devnet`
aliases are accepted. The claim endpoint returns `{ok, claimable, transactions,
blockhash: {blockhash, lastValidBlockHeight}}`. It never signs or broadcasts.
Status returns `{ok, claimable, txCount}`. Metaplex's documented HTTP 400
`No rewards available to claim` becomes a normal `claimable:false` response;
provider failures, malformed payloads and rate limits are not zero balances.
These responses are not cached.

Standalone SPL token creation does not itself accrue Genesis fees. Locked-LP
Fee Keys, unrelated marketplace royalties, Meteora fees and MPL-3643 issuance
are not covered by these claim controls. No universal claim-all across every
Solana protocol is implied.

Reference: [Metaplex creator-reward API](https://www.metaplex.com/docs/api/claim-creator-rewards).

## Launch and Asset Discovery

Explore lists the public Metaplex Genesis index. Filter by network, live/upcoming/
graduated status, and curated spotlight. Look up one Genesis address or all
campaigns associated with a token mint. One token may have multiple campaigns;
Musebook preserves the array rather than choosing an arbitrary launch.
The upstream list is not paginated; the UI pages the returned list locally.

The Assets / DAS view supports exact asset lookup and paginated wallet-owner
discovery, with an optional Core-only filter. It uses the official
`@metaplex-foundation/digital-asset-standard-api` Umi plugin and
`@metaplex-foundation/mpl-core-das` conversion/collection-plugin derivation.
Core collection reads use normal RPC while indexed DAS reads use a separate
read-only gateway. Registered agents can be opened in the Genesis workspace,
where fresh on-chain owner checks still apply before signing.

Indexed ownership, canonical agent tokens and external adapters are labeled as
indexed data, not authorization or proof of current on-chain state. Fungible
inspection additionally uses the Token Metadata SDK to read exact on-chain
supply, decimals, mint/freeze authorities and metadata update authority.
Missing provider data is an error/unavailable state, not a zero balance.

### Public Read API

| Method | Path | Parameters |
| --- | --- | --- |
| GET | `/api/metaplex/launches` | `network`, `status`, `spotlight` |
| GET | `/api/metaplex/launches/{genesis}` | `network` |
| GET | `/api/metaplex/tokens/{mint}` | `network` |
| POST | `/api/metaplex/das` | `network=mainnet` or `devnet`; JSON-RPC body |

REST launch reads use `network=solana-mainnet` (default) or `solana-devnet`.
Spotlight is `/launches?spotlight=true`, not a separate endpoint. Listing data
is returned inside `data`, following the Metaplex REST API.

```bash
curl 'https://musebook.trade/api/metaplex/launches?spotlight=true&network=solana-mainnet'

curl 'https://musebook.trade/api/metaplex/das?network=mainnet' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"getAsset","params":{"id":"BDvrsTy4Rugy7doh4h23HqdRtPjZ4n6fwhocQV4DgMdM"}}'
```

The gateway allows `getAsset`, `getAssets` (1-50 IDs), `getAssetsByOwner`, and
owner-scoped `searchAssets` with `interface=MplCoreAsset`. Owner queries use
`ownerAddress`, page 1-1000 and limit 1-50. Arbitrary RPC methods, transaction
broadcasts, arbitrary upstream URLs and JSON-RPC request batches are rejected.
Rate limits, timeouts, body limits and redacted provider errors apply.

Server configuration uses the existing `HELIUS_API_KEY`, or optional
`SOLANA_DAS_RPC_URL` / `SOLANA_DEVNET_DAS_RPC_URL` overrides. These are server
secrets, never `VITE_` values. A provider may need DAS enabled for its endpoint.

## Standalone Fungible Tokens

Create token uses official Token Metadata and Toolbox SDK builders. It creates
a legacy SPL mint with Metaplex metadata and mints the exact initial supply to
the creator wallet's associated token account in **one atomic transaction**.
This does not create a Genesis sale, market/liquidity pool, RWA compliance layer
or canonical agent-token binding.

1. Choose a network (devnet by default), name, symbol, hosted HTTPS metadata
   JSON URI, decimals (0-9) and initial supply as a decimal string.
2. Connect the creator wallet. Token name/URI limits are checked in UTF-8 bytes;
   supply uses integer base units and must fit SPL's u64 range.
3. Mint and freeze authorities remain with the creator by default. Optional
   permanent revocation requires a separate acknowledgement. Metadata remains
   mutable with the creator as its update authority.
4. Review the exact generated mint, associated account, network, supply and
   authority settings. Review simulates without prompting for a signature.
   Rent and network-fee estimates include the new token account; additional
   [Metaplex protocol fees](https://www.metaplex.com/docs/protocol-fees) may apply.
5. Explicitly sign and create. The app rebuilds with a fresh blockhash,
   simulates again, signs with the temporary mint signer and browser wallet,
   saves the expected signature, then broadcasts with preflight enabled.
6. A pending receipt blocks duplicate creation. Check status after a reload
   without signing or rebroadcasting. Confirmation is matched to the recorded
   wallet and newly created mint, not just any successful transaction.

The temporary mint key is held in memory only and is never exported or saved.
Receipts contain public parameters and signatures, not wallet keys or signed
transaction bytes. Unknown receipts stay pending; retain an export before
manual reconciliation or clearing site storage.

## Permissioned Assets

`/launchpad/?mode=mpl3643` uses the same validated planner, read API, saved drafts,
and JSON export format as [Agent Assets](RWA-AGENTS.md). Issuance plans and market
pairing proposals can be reviewed without signing. Exact mint inspections and
canonical agent-token checks do not create a pool or replace an agent's token.

**MPL-3643 execution remains disabled.** Alpha access, approved SDK integration,
issuer/attestor verification and operational readiness are still required.
`POST /api/rwa/prepare` remains HTTP 503 `MPL3643_ALPHA_REQUIRED` with no transactions.

## Genesis Agent Tokens

Open `/launchpad/?mode=genesis` for the bonding-curve launch flow:

1. Choose mainnet or devnet. The directory picker lists mainnet agents; a devnet
   agent must exist on devnet and be entered explicitly.
2. Inspect the exact Core asset. The workspace reads the Core owner and Agent
   Identity plugin on-chain, derives its Asset Signer using the Metaplex SDK,
   and reads that address's SOL balance.
3. Enter token metadata and an existing Irys image URL. Mainnet image uploads
   have a separate quote and approval action. Uploads may spend real SOL even
   before a token launch; this uploader is disabled in devnet mode.
4. Enter a first-buy amount in SOL, with up to nine decimal places. The Asset
   Signer must hold that amount. Network fees and account rent are additional.
5. Connect the current Core asset owner's wallet and review the launch. This
   workspace does not support delegated authority. It does not infer authority
   from a directory listing or from a derived PDA.
6. Approve the launch explicitly, then review each wallet transaction. The
   Metaplex API supplies the transaction batch. Transactions are simulated,
   signed in the browser, sent with preflight, and confirmed individually.
7. The workspace registers the launch only after confirmed success and presents
   the mint, signatures, and Metaplex link in a receipt.

Wallet prompts and explorer links use the selected network. RPC credentials
remain on Musebook's server. Musebook does not read local keypairs or sign on
behalf of the user.

### Canonical Token Binding

Permanent binding defaults off. It is disabled on devnet, when the canonical
token index is unavailable, or when an existing binding is reported. On mainnet
it requires a fresh inspection and an explicit irreversible-action acknowledgement.
The chain and Metaplex API still enforce the actual binding constraints; a
missing indexed token is not proof of absence on-chain.

Pairing an existing agent token with a stock or RWA is a separate proposal. It
does not require creating a new canonical token. See [Agent Assets](RWA-AGENTS.md).

### Drafts and Recovery

- Save/restore retains one Genesis form draft in browser-local storage.
  Restoring a draft never restores permanent-binding approval.
- A launch receipt is saved before broadcasting, including the expected
  transaction signature. A timeout can still result in an on-chain transaction.
- A pending receipt blocks another launch. Mainnet and devnet explorer links
  are attached to the receipt's original network, not the current form.
- **Check status / register** rereads confirmation status and retries registration
  only when the entire recorded batch is confirmed. It does not create a new
  token, rebroadcast transactions, or request another signature.
- Partial batches, failed transactions and unknown signatures require
  reconciliation. Automatic completion of a partially submitted batch is not
  supported; retain the exported receipt and inspect the chain before acting.
- An empty attempt with no submitted signatures can be discarded. A confirmed
  receipt can be closed. Submitted unresolved receipts are not silently cleared.
- Do not clear site storage while a launch is unresolved. Drafts and receipts
  are plaintext local data, not a hosted backup or encrypted custody.

The original creator wallet is retained for registration recovery after reload.
Closing the workspace stops additional wallet prompts; an already-sent
transaction can still confirm. Browser launch locks prevent duplicate starts
across tabs in browsers that support the Web Locks API.

## Verification Boundary

Unit tests cover owner and network checks, invalid amounts, simulation failures,
expiry, wallet rejection/switching, changed transaction messages, confirmation
errors, pending receipts, and registration-only recovery. Browser tests use
isolated RPC/API and wallet fixtures for signing and broadcasting behavior.
Live read checks and draft planning are separate evidence from a funded launch.

Additional tests cover DAS method/parameter limits, server credential redaction,
upstream errors, exact fungible amounts and atomic SDK instructions. Token
creation browser fixtures cover success, rejected signing, failed simulation,
and reload recovery with no second signature or broadcast.

Optional X/Twitter verification is not enabled in this workspace. It requires
an application OAuth consent flow with `users.read` before calling Metaplex's
`/twitter/verify`; a typed social link alone is not verified. Launch registration
continues without a verification token. No OAuth access token is requested or
stored by these new controls. Existing creator-reward operations remain on
[/claim](https://musebook.trade/claim).

**No funded mainnet launch was performed as part of this upgrade.** Neither the
UI nor passing tests imply Metaplex approval, successful issuance of a real
asset, or a complete protocol/dependency security audit.

Reference: [Metaplex Genesis API client](https://www.metaplex.com/docs/smart-contracts/genesis/sdk/api-client).
