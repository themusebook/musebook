# Privy Solana

Solana wallets, networks, and transaction signing (signAndSendTransaction, signMessage, signTransaction). Source: https://docs.privy.io/llms-full.txt

# Advanced swap (Solana)
Source: https://docs.privy.io/api-reference/labs/advanced-swap

post /v1/wallets/{wallet_id}/experimental/solana/advanced-swap
Execute a low-latency synchronous Solana token swap with an embedded wallet.

<Warning>
  This is a [Privy Labs API](/api-reference/labs/overview). It is subject to change as Privy
  iterates on the design with partners. Privy provides at least three months of notice before
  removing a documented Labs API.
</Warning>

### Overview

The advanced swap endpoint performs a synchronous Solana token swap in a single request: Privy
fetches a quote, signs the transaction via the enclave, and submits it to the network. Wallet data
preparation is parallelized with the swap quote fetching to minimize latency.

Unlike the standard [swap endpoint](/api-reference/wallets/swap/tokens), this endpoint returns the
signed transaction directly rather than creating an asynchronous wallet action.

To learn more about the design of this endpoint, see [our blog post on reducing trading latency](https://privy.io/blog/reducing-trading-latency-on-privy).

### Prerequisites

* The wallet must be a **Solana** embedded wallet
* Your app must be approved for access to this Labs endpoint

***

### Considerations

This endpoint behaves similarly to [`optimistic_broadcast`](/api-reference/wallets/solana/sign-and-send-transaction) on the standard Solana sign-and-send endpoint:

* The response is returned as soon as the transaction is signed and submitted, it does not wait for onchain confirmation.
* The `submission_status` field indicates whether the network acknowledged the transaction, not whether it confirmed onchain. Monitor the returned `transaction_hash` via Solana RPC for final status.
* The `signed_transaction` field contains the fully signed transaction (base64-encoded), which can be rebroadcast to any Solana RPC endpoint for redundancy or improved landing rates.
* Your app is responsible for checking transaction validity and rebroadcasting if needed.




# tron_sendTransaction
Source: https://docs.privy.io/api-reference/wallets/tron/tron-send-transaction

Sign and broadcast a Tron transaction in one call

Sign a Tron transaction and broadcast it to the network. Privy automatically fetches block reference fields (`ref_block_bytes`, `ref_block_hash`, `expiration`) if you omit them.

<Info>
  To sign without broadcasting — for example when using a custom RPC or gas sponsor — use
  [`tron_signTransaction`](/api-reference/wallets/tron/tron-sign-transaction) instead.
</Info>

<Warning>
  The wallet RPC endpoint is a synchronous endpoint, and a successful response indicates that the
  transaction has been broadcasted to the network. Transactions may get broadcasted but still fail
  to be confirmed by the network. The endpoint does not wait for confirmation or retry if the
  transaction fails to be confirmed. To handle these scenarios, see our guide on [speeding up
  transactions](/recipes/speeding-up-transactions).
</Warning>

### SDK methods

Learn more about sending Tron transactions using our SDKs [here](/wallets/using-wallets/tron/send-a-transaction).

***

<Warning>
  **Idempotency on errors:** On 4xx or 5xx, Privy caches the response and replays it for the same
  key. Generate a new key to retry after a server error. Policy violations are an exception and
  allow same-key retries.
</Warning>

<RequestExample>
  ```sh TRX transfer theme={"system"} theme={"system"}
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "tron_sendTransaction",
    "caip2": "tron:mainnet",
    "params": {
      "raw_data": {
        "contract": [
          {
            "type": "TransferContract",
            "owner_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
            "to_address": "41e552f6487585c2b58bc2c9bb4492bc1f17132cd0",
            "amount": 1000000
          }
        ]
      }
    }
  }'
  ```

  ```sh TRC-20 transfer theme={"system"} theme={"system"}
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "tron_sendTransaction",
    "caip2": "tron:mainnet",
    "params": {
      "raw_data": {
        "contract": [
          {
            "type": "TriggerSmartContract",
            "owner_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
            "contract_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
            "data": "a9059cbb000000000000000041e552f6487585c2b58bc2c9bb4492bc1f17132cd000000000000000000000000000000000000000000000000000000000000f4240",
            "call_value": 0
          }
        ],
        "fee_limit": 100000000
      },
      "reference_id": "my-idempotency-key-123"
    }
  }'
  ```
</RequestExample>

<ResponseExample>
  ```json 200 theme={"system"} theme={"system"}
  {
    "method": "tron_sendTransaction",
    "data": {
      "hash": "8a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1",
      "caip2": "tron:mainnet",
      "transaction_id": "8a3f2b1c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1"
    }
  }
  ```
</ResponseExample>

### Headers

<ParamField type="string">
  ID of your Privy app.
</ParamField>

<ParamField type="string">
  Request authorization signature. If multiple signatures are required, they should be comma
  separated.
</ParamField>

### Path Parameters

<ParamField type="string">
  ID of the Tron wallet to sign and send with.
</ParamField>

### Body

<ParamField type="string">
  Must be `"tron_sendTransaction"`.
</ParamField>

<ParamField type="string">
  Tron CAIP-2 chain. Defaults to `tron:mainnet`. Use `tron:nile` for the Nile testnet.
</ParamField>

<ParamField type="object">
  <Expandable title="properties">
    <ParamField type="object">
      <Expandable title="properties">
        <ParamField type="array">
          Array of exactly one contract object. Use `TransferContract` for native TRX transfers; use `TriggerSmartContract` for TRC-20 transfers and other smart contract calls. All addresses must be 41-prefixed hex (use `TronWeb.address.toHex()` to convert from base58check).

          **TransferContract:**

          * `type`: `"TransferContract"`
          * `owner_address`: sender, 41-prefixed hex
          * `to_address`: recipient, 41-prefixed hex
          * `amount`: sun (1 TRX = 1,000,000 sun)

          **TriggerSmartContract:**

          * `type`: `"TriggerSmartContract"`
          * `owner_address`: caller, 41-prefixed hex
          * `contract_address`: contract, 41-prefixed hex
          * `data` (optional): ABI-encoded calldata, hex string
          * `call_value` (optional): TRX value in sun sent with the call
          * `call_token_value` (optional): TRC-10 token value
          * `token_id` (optional): TRC-10 token ID
        </ParamField>

        <ParamField type="number">
          Maximum energy fee in sun. Required for `TriggerSmartContract`. `100_000_000` (100 TRX) is a safe default for standard TRC-20 transfers.
        </ParamField>

        <ParamField type="string">
          Block reference bytes — 4 hex characters. Optional — Privy fetches fresh values if omitted.
        </ParamField>

        <ParamField type="string">
          Block reference hash — 16 hex characters. Optional — Privy fetches fresh values if omitted.
        </ParamField>

        <ParamField type="number">
          Expiration in Unix milliseconds. Optional — Privy sets `now + 60s` if omitted.
        </ParamField>

        <ParamField type="number">
          Creation timestamp in Unix milliseconds. Defaults to `Date.now()` if omitted.
        </ParamField>

        <ParamField type="string">
          Transaction memo, hex-encoded. Distinct from `TriggerSmartContract.data` (calldata).
        </ParamField>
      </Expandable>
    </ParamField>

    <ParamField type="string">
      Optional idempotency key (max 64 characters). Re-submitting the same `reference_id` returns the cached response.
    </ParamField>
  </Expandable>
</ParamField>

### Returns

<ResponseField name="method" type="string">
  Always `"tron_sendTransaction"`.
</ResponseField>

<ResponseField name="data.hash" type="string">
  Tron transaction ID — SHA-256 of the raw transaction bytes, lowercase hex, no `0x` prefix.
</ResponseField>

<ResponseField name="data.caip2" type="string">
  The CAIP-2 chain the transaction was broadcast on.
</ResponseField>

<ResponseField name="data.transaction_id" type="string">
  Privy internal transaction ID.
</ResponseField>

<ResponseField name="data.reference_id" type="string">
  Echoed back if provided in the request.
</ResponseField>




# tron_signTransaction
Source: https://docs.privy.io/api-reference/wallets/tron/tron-sign-transaction

Sign a Tron transaction without broadcasting it

Sign a Tron transaction using the wallet's private key. Returns the full signed transaction hex — you are responsible for broadcasting it.

<Info>
  For a combined sign-and-broadcast call, use
  [`tron_sendTransaction`](/api-reference/wallets/tron/tron-send-transaction) instead.
</Info>

***

<Warning>
  **Idempotency on errors:** On 4xx or 5xx, Privy caches the response and replays it for the same
  key. Generate a new key to retry after a server error. Policy violations are an exception and
  allow same-key retries.
</Warning>

<RequestExample>
  ```sh TRX transfer theme={"system"} theme={"system"}
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "tron_signTransaction",
    "params": {
      "raw_data": {
        "contract": [
          {
            "type": "TransferContract",
            "owner_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
            "to_address": "41e552f6487585c2b58bc2c9bb4492bc1f17132cd0",
            "amount": 1000000
          }
        ],
        "ref_block_bytes": "a2b4",
        "ref_block_hash": "1234567890abcdef",
        "expiration": 1735689600000,
        "timestamp": 1735689540000
      }
    }
  }'
  ```

  ```sh TRC-20 transfer theme={"system"} theme={"system"}
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "tron_signTransaction",
    "params": {
      "raw_data": {
        "contract": [
          {
            "type": "TriggerSmartContract",
            "owner_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
            "contract_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
            "data": "a9059cbb000000000000000041e552f6487585c2b58bc2c9bb4492bc1f17132cd000000000000000000000000000000000000000000000000000000000000f4240",
            "call_value": 0
          }
        ],
        "ref_block_bytes": "a2b4",
        "ref_block_hash": "1234567890abcdef",
        "expiration": 1735689600000,
        "timestamp": 1735689540000,
        "fee_limit": 100000000
      }
    }
  }'
  ```
</RequestExample>

<ResponseExample>
  ```json 200 theme={"system"} theme={"system"}
  {
    "method": "tron_signTransaction",
    "data": {
      "signed_transaction": "0a02a2b42208...",
      "encoding": "hex"
    }
  }
  ```
</ResponseExample>

### Headers

<ParamField type="string">
  ID of your Privy app.
</ParamField>

<ParamField type="string">
  Request authorization signature. If multiple signatures are required, they should be comma
  separated.
</ParamField>

### Path Parameters

<ParamField type="string">
  ID of the Tron wallet to sign with.
</ParamField>

### Body

<ParamField type="string">
  Must be `"tron_signTransaction"`.
</ParamField>

<ParamField type="object">
  <Expandable title="properties">
    <ParamField type="object">
      <Expandable title="properties">
        <ParamField type="array">
          Array of exactly one contract object. Use `TransferContract` for native TRX transfers; use `TriggerSmartContract` for TRC-20 transfers and other smart contract calls. All addresses must be 41-prefixed hex (use `TronWeb.address.toHex()` to convert from base58check).

          **TransferContract:**

          * `type`: `"TransferContract"`
          * `owner_address`: sender, 41-prefixed hex
          * `to_address`: recipient, 41-prefixed hex
          * `amount`: sun (1 TRX = 1,000,000 sun)

          **TriggerSmartContract:**

          * `type`: `"TriggerSmartContract"`
          * `owner_address`: caller, 41-prefixed hex
          * `contract_address`: contract, 41-prefixed hex
          * `data` (optional): ABI-encoded calldata, hex string
          * `call_value` (optional): TRX value in sun sent with the call
          * `call_token_value` (optional): TRC-10 token value
          * `token_id` (optional): TRC-10 token ID
        </ParamField>

        <ParamField type="string">
          Block reference bytes — 4 hex characters. Must be fetched fresh from chain before signing (expires in \~60s). Use `TronWeb.trx.getCurrentRefBlockParams()`.
        </ParamField>

        <ParamField type="string">
          Block reference hash — 16 hex characters. Fetched alongside `ref_block_bytes`.
        </ParamField>

        <ParamField type="number">
          Transaction expiration in Unix milliseconds.
        </ParamField>

        <ParamField type="number">
          Transaction creation timestamp in Unix milliseconds. Defaults to `Date.now()` if omitted.
        </ParamField>

        <ParamField type="number">
          Maximum energy fee in sun. Required for `TriggerSmartContract`. `100_000_000` (100 TRX) is a safe default for standard TRC-20 transfers.
        </ParamField>

        <ParamField type="string">
          Transaction memo, hex-encoded. Distinct from `TriggerSmartContract.data` (calldata).
        </ParamField>
      </Expandable>
    </ParamField>
  </Expandable>
</ParamField>

### Returns

<ResponseField name="method" type="string">
  Always `"tron_signTransaction"`.
</ResponseField>

<ResponseField name="data.signed_transaction" type="string">
  The signed transaction hex: `rawDataHex + signatureHex`. The signature occupies the last 130 hex
  characters (65 bytes). Pass directly to `POST /wallet/broadcasthex` on a Tron full node, or use
  `TronWeb.trx.sendRawTransaction()`.
</ResponseField>

<ResponseField name="data.encoding" type="string">
  Always `"hex"`.
</ResponseField>




# Configuring Solana networks
Source: https://docs.privy.io/basics/react/advanced/configuring-solana-networks

Configure Solana RPC endpoints and clusters (mainnet, devnet, testnet) in the PrivyProvider using createSolanaRpc

Privy supports [Solana clusters](https://solana.com/docs/core/clusters) such as Mainnet Beta, Devnet, and Testnet.

To configure RPC endpoints for Solana when using the Privy embedded wallet UIs (UI `signTransaction` and `signAndSendTransaction`), set RPC clients under the `config.solana.rpcs` prop of the `PrivyProvider`:

```tsx theme={"system"}
<PrivyProvider
  appId="your-privy-app-id"
  config={{
    ...theRestOfYourConfig,
    solana: {
      rpcs: {
        'solana:mainnet': {
          rpc: createSolanaRpc('https://api.mainnet-beta.solana.com'),
          rpcSubscriptions: createSolanaRpcSubscriptions('wss://api.mainnet-beta.solana.com')
        },
        'solana:devnet': {
          rpc: createSolanaRpc('https://api.devnet.solana.com'),
          rpcSubscriptions: createSolanaRpcSubscriptions('wss://api.devnet.solana.com')
        }
      }
    }
  }}
>
  {/* your app's content */}
</PrivyProvider>
```

<Info>
  The `config.solana.rpcs` configuration is only required for Privy's embedded wallet UIs. If you
  are using external Solana wallets (e.g., Phantom, Solflare) without embedded wallet UIs, you do
  not need to set `config.solana.rpcs`.
</Info>
