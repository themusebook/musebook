# Market and Paired-Token Workspaces

## Pages

| Page | Data and actions |
| --- | --- |
| [/stocks/](https://musebook.trade/stocks/) | META daily OHLCV from Massive, labeled daily closes, plus a separate Backpack securities catalog. |
| [/market/](https://musebook.trade/market/) | Alias of `/markets/`. OpenMarket Binance Futures candles, volume, open interest, funding and liquidations; separate Backpack ticker, orderbook and recent trades. |
| [/stonkfun/](https://musebook.trade/stonkfun/) | Token discovery, paired-token launches and the Jupiter/DFlow swap desk. |
| [/launchpad/?mode=paired](https://musebook.trade/launchpad/?mode=paired) | Shared paired-token launch form with searchable quote-asset tiles and a review summary. Existing Metaplex and permissioned-asset modes remain separate. |

Daily closes are not intraday quotes. Provider errors, stale observations and plan limits remain visible. The OpenMarket heatmap costs 10 weight and is blocked by the client's half-budget guard on the Free tier. Other plans remain subject to their provider permissions and limits. Missing data is not a zero price.

## Launch a Paired Token

1. Choose an eligible quote asset. Both `launchable` and `launchLabReady` must be true in Stonk.fun's public pair catalog.
2. Enter a name, symbol and public HTTPS or IPFS metadata JSON URI, then connect a Solana wallet.
3. Prepare and review the new mint, quote asset, curve pricing, estimated fees and account rent. Reviews expire after 45 seconds. This form exposes standard launches only: no transfer tax, holder-payout basket or initial buy.
4. Approve the simulated mainnet transaction in your wallet. The browser builds with the Raydium SDK and keeps the ephemeral mint signer local. Wallet keys never enter the page or server.
5. Wait for confirmation. The public signature is stored before broadcast. After a timeout or reload, use **Check status**; do not create a replacement while the original is unresolved.
6. Confirmation and venue adoption are tracked separately. Confirmed receipts enter the server-verified site-launch feed for Convex indexing. Indexing can lag or retry without another signature.

Recovery is read-only. A missing transaction is only considered expired after finalized block-height expiry, a second signature lookup and verification that the mint does not exist. Reloaded receipt status is rechecked against the chain.

LaunchLab creator fees are forwarded after adoption, not shown as manually claimable balances. Legacy Stonk.fun Fee Key NFT claims are a different API workflow and are not implemented by this form. Token creation does not guarantee liquidity or a Jupiter route.

## Trade

Selecting a listed token checks its mint decimals on-chain before prefilling the swap desk. Trading uses the site's existing server-authenticated Jupiter/DFlow flow: fresh quote, exact transaction review, wallet signature, execution and pending-receipt reconciliation. It does not use the legacy unauthenticated Jupiter V1 helper. The separate Town helper is unchanged.

Trading and launching require explicit wallet approval. No automated tests spend funds. These workflows are not financial advice.

## Operator Configuration

Keep all provider credentials server-side, never in `VITE_` variables or source control:

| Variable | Purpose |
| --- | --- |
| `MASSIVE_API_KEY` | META daily bars via `/api/stocks/meta`. |
| `OPENMARKET_API_KEY` | Proxied OpenMarket history and metadata requests. |
| `JUPITER_API_KEY` | Existing server-side swap quote, build and managed execution. |
| Existing DFlow and Solana RPC settings | Swap routing, chain inspection, simulation and signed-transaction relay. |

Stonk.fun public market reads require no API key. MPL-3643 issuance remains access-gated and is not enabled by this paired-token form. This public repository documents the app; it does not contain the private frontend or add a new CLI launch command.

## Verification Boundary

The private frontend includes `market-launch.test.mjs`, `stonk-launch-browser.mjs` and `market-pages-browser.mjs`. Coverage includes launch-policy validation, SDK account layout, wallet rejection, lost-response recovery, expired non-landed transactions, disabled venues, feed reporting and 1440/390/320px layouts. Launch signing tests use isolated fixtures with every RPC and venue mutation intercepted. Live-provider reads and rendered charts are checked separately.

Passing these checks does **not** establish funded mainnet launch or swap success. Production releases must also verify the canonical `/release.json`, route chunks and live API responses.
