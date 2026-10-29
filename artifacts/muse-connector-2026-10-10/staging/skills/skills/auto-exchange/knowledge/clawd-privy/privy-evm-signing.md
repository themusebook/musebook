# Privy EVM Signing

EVM transaction signing: eth_sendTransaction, personal_sign, signTypedData, wallet_sendCalls, smart wallets. Source: https://docs.privy.io/llms-full.txt

# Get user by smart wallet address
Source: https://docs.privy.io/api-reference/users/get-by-smart-wallet-address

post /v1/users/smart_wallet/address
Looks up a user by their smart wallet address.





# eth_sendTransaction
Source: https://docs.privy.io/api-reference/wallets/ethereum/eth-send-transaction

post /v1/wallets/{wallet_id}/rpc
Sign and send a transaction using the eth_sendTransaction method.

### SDK methods

Learn more about sending transactions using our SDKs [here](/wallets/using-wallets/ethereum/send-a-transaction).

***

<Warning>
  **Idempotency on errors:** On 4xx or 5xx, Privy caches the response and replays it for the same
  key. Generate a new key to retry after a server error. Policy violations are an exception and
  allow same-key retries.
</Warning>

<RequestExample>
  ```sh Without sponsorship theme={"system"}
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "eth_sendTransaction",
    "caip2": "eip155:11155111",
    "chain_type": "ethereum",
    "params": {
      "transaction": {
        "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "value": "0x2386F26FC10000"
      }
    }
  }'
  ```

  ```sh With sponsorship theme={"system"}
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
    "method": "eth_sendTransaction",
    "caip2": "eip155:11155111",
    "chain_type": "ethereum",
    "sponsor": true,
    "params": {
      "transaction": {
        "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "value": "0x2386F26FC10000"
      }
    }
  }'
  ```
</RequestExample>

<ResponseExample>
  ```json Without sponsorship theme={"system"}
  {
    "method": "eth_sendTransaction",
    "data": {
      "hash": "0xfc3a736ab2e34e13be2b0b11b39dbc0232a2e755a11aa5a9219890d3b2c6c7d8",
      "caip2": "eip155:11155111",
      "transaction_id": "y90vpg3bnkjxhw541c2zc6a9",
      "transaction_request": {
        "to": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "value": "0x2386F26FC10000",
        "chain_id": 11155111,
        "type": 2,
        "nonce": 5,
        "max_fee_per_gas": "0xF4834",
        "max_priority_fee_per_gas": "0xF4240",
        "gas_limit": "0xC350"
      }
    }
  }
  ```

  ```json With sponsorship theme={"system"}
  {
    "method": "eth_sendTransaction",
    "data": {
      "hash": "",
      "user_operation_hash": "0x8f3a4e7d2c1b9a5e6f4d3c2b1a9e8f7d6c5b4a3e2d1c0b9a8f7e6d5c4b3a2e1d",
      "caip2": "eip155:11155111",
      "transaction_id": "y90vpg3bnkjxhw541c2zc6a9"
    }
  }
  ```
</ResponseExample>

<Warning>
  The wallet RPC endpoint is a synchronous endpoint, and a successful response indicates that the
  transaction has been broadcasted to the network. Transactions may get broadcasted but still fail
  to be confirmed by the network. The endpoint does not wait for confirmation or retry if the
  transaction fails to be confirmed. To handle these scenarios, see our guide on [speeding up
  transactions](/recipes/speeding-up-transactions).
</Warning>

### Headers

<ParamField type="string">
  ID of your Privy app.
</ParamField>

<ParamField type="string">
  Request authorization signature. If multiple signatures are required, they should be comma
  separated.
</ParamField>

<ParamField type="string">
  Request expiry. Value is a Unix timestamp in milliseconds representing the deadline by which the
  request must be processed.
</ParamField>

### Path Parameters

<ParamField type="string">
  ID of the wallet to get.
</ParamField>

### Body

<ParamField type="string">
  Available options: `eth_sendTransaction`
</ParamField>

<ParamField type="string" />

<ParamField type="object">
  <Expandable title="child attributes">
    <ParamField type="object">
      <Expandable title="child attributes">
        <ParamField type="string" />

        <ParamField type="string | number" />

        <ParamField type="string | number" />

        <ParamField type="number">
          Available options: `0`, `1`, `2`, `4`.
        </ParamField>

        <ParamField type="string | number" />

        <ParamField type="string | number" />

        <ParamField type="string | number" />

        <ParamField type="string" />

        <ParamField type="string" />

        <ParamField type="string | number" />

        <ParamField type="string | number" />

        <ParamField type="object[]">
          Applies to EIP-7702 type-4 transactions.

          <Expandable title="child attributes">
            <ParamField type="string">
              The delegated contract address.
            </ParamField>

            <ParamField type="string | number" />

            <ParamField type="string | number" />

            <ParamField type="string" />

            <ParamField type="string" />

            <ParamField type="0 | 1" />
          </Expandable>
        </ParamField>
      </Expandable>
    </ParamField>
  </Expandable>
</ParamField>

<ParamField type="boolean">
  Optional parameter to enable gas sponsorship for this transaction. [Learn
  more.](/wallets/gas-and-asset-management/gas/overview)
</ParamField>

<ParamField type="object">
  Options for [user pays](/wallets/gas-and-asset-management/gas/setup#user-pays) gas sponsorship, in
  which the wallet covers gas with a stablecoin balance instead of the app's gas credits. Requires
  `sponsor: true` and an app configured for user pays mode. Not supported on Tempo.

  <Expandable title="child attributes">
    <ParamField type="string">
      The token the wallet pays gas with, such as `usdc` or `usdt`. Must be enabled for this chain in
      the dashboard. See the [supported chains and
      tokens](/wallets/gas-and-asset-management/gas/setup#user-pays).
    </ParamField>
  </Expandable>
</ParamField>

<ParamField type="string">
  Optional developer-provided reference ID for transaction reconciliation. Must be unique per
  transaction and up to 64 characters. Use this to correlate transactions with your own internal
  records. The `reference_id` is included in [transaction
  webhook](/api-reference/webhooks/transaction/broadcasted) payloads and can be used to [look up
  transactions](/api-reference/transactions/external-id).
</ParamField>

<ParamField type="string" />

<ParamField type="string">
  Available options: `ethereum`
</ParamField>

### Returns

<ResponseField name="method" type="enum<string>">
  Available options: `eth_sendTransaction`
</ResponseField>

<ResponseField name="data" type="object">
  <Expandable title="child attributes">
    <ResponseField name="hash" type="string">
      The transaction hash. For paymaster-sponsored transactions, returns an empty string until the
      transaction confirms on-chain.
    </ResponseField>

    <ResponseField name="user_operation_hash" type="string">
      The user operation hash. Only present for standard EVM paymaster-sponsored transactions.
    </ResponseField>

    <ResponseField name="transaction_request" type="object">
      The full transaction object that was signed and broadcast. Contains the resolved transaction
      fields including `to`, `value`, `chain_id`, `nonce`, `gas_limit`, and fee parameters.
    </ResponseField>

    <ResponseField name="caip2" type="string" />

    <ResponseField name="transaction_id" type="string" />

    <ResponseField name="reference_id" type="string | null">
      The developer-provided reference ID, if one was provided in the request.
    </ResponseField>
  </Expandable>
</ResponseField>




# eth_sign7702Authorization
Source: https://docs.privy.io/api-reference/wallets/ethereum/eth-sign-7702-authorization

post /v1/wallets/{wallet_id}/rpc
Signs an EIP-7702 authorization struct using the wallet's private key.

### SDK methods

Learn more about signing EIP-7702 authorizations using our SDKs [here](/wallets/using-wallets/ethereum/sign-7702-authorization).

***

<Warning>
  **Idempotency on errors:** On 4xx or 5xx, Privy caches the response and replays it for the same
  key. Generate a new key to retry after a server error. Policy violations are an exception and
  allow same-key retries.
</Warning>

<RequestExample>
  ```sh cURL theme={"system"}
  curl --request POST \
    --url https://api.privy.io/v1/wallets/{wallet_id}/rpc \
    --header 'Authorization: Basic <encoded-value>' \
    --header 'Content-Type: application/json' \
    --header 'privy-app-id: <privy-app-id>' \
    --data '{
      "method": "eth_sign7702Authorization",
      "params": {
        "contract": "0x1234567890abcdef1234567890abcdef12345678",
        "chain_id": 1,
        "nonce": 0
      }
  }'
  ```
</RequestExample>

<ResponseExample>
  ```json 200 theme={"system"}
  {
    "method": "eth_sign7702Authorization",
    "data": {
      "authorization": {
        "contract": "0x1234567890abcdef1234567890abcdef12345678",
        "chain_id": 1,
        "nonce": 0,
        "r": "0x0db9c7bd881045cbba28c347de6cc32a653e15d7f6f2f1cec21d645f402a6419",
        "s": "0x6e877eb45d3041f8d2ab1a76f57f408b63894cfc6f339d8f584bd26efceae308",
        "y_parity": 1
      }
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

<ParamField type="string">
  Request expiry. Value is a Unix timestamp in milliseconds representing the deadline by which the
  request must be processed.
</ParamField>

### Path Parameters

<ParamField type="string">
  ID of the wallet to get.
</ParamField>

### Body

<ParamField type="string">
  The RPC method to execute. Must be `eth_sign7702Authorization`.
</ParamField>

<ParamField type="object">
  The parameters for signing the EIP-7702 authorization.

  <Expandable title="child properties">
    <ParamField type="string">
      The address of the smart contract that the EOA will delegate to. Must be a valid Ethereum
      address in hex format.
    </ParamField>

    <ParamField type="number">
      The chain ID where this authorization will be valid.
    </ParamField>

    <ParamField type="number">
      The nonce for the authorization. If not provided, we will fetch the current nonce for the
      wallet.
    </ParamField>
  </Expandable>
</ParamField>

### Response

<ResponseField name="method" type="string">
  The RPC method that was executed. Will be `eth_sign7702Authorization`.
</ResponseField>

<ResponseField name="data" type="object">
  The response data containing the signed authorization.

  <Expandable title="child properties">
    <ResponseField name="authorization" type="object">
      The signed EIP-7702 authorization object.

      <Expandable title="authorization properties">
        <ResponseField name="contract" type="string">
          The address of the smart contract that the EOA delegates to.
        </ResponseField>

        <ResponseField name="chain_id" type="number">
          The chain ID where this authorization is valid.
        </ResponseField>

        <ResponseField name="nonce" type="number">
          The nonce for the authorization.
        </ResponseField>

        <ResponseField name="r" type="string">
          The r component of the ECDSA signature.
        </ResponseField>

        <ResponseField name="s" type="string">
          The s component of the ECDSA signature.
        </ResponseField>

        <ResponseField name="y_parity" type="number">
          The recovery parameter (0 or 1) for the signature.
        </ResponseField>
      </Expandable>
    </ResponseField>
  </Expandable>
</ResponseField>
