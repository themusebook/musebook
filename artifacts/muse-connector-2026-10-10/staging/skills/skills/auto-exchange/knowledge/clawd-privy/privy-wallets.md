# Privy Wallets

Embedded wallets: creation, HD wallets, export, import, recovery, smart wallets, server/agent wallets. Source: https://docs.privy.io/llms-full.txt

# Pregenerate wallets
Source: https://docs.privy.io/api-reference/users/pregenerate-wallets

post /v1/users/{user_id}/wallets
Creates an embedded wallet for an existing user.

### SDK methods

Learn more about pregenerating wallets using our SDKs [here](/recipes/pregenerate-wallets).




# Create wallet automation
Source: https://docs.privy.io/api-reference/wallet-automations/create

post /v1/wallet_automations
Create a reusable wallet automation definition.





# Get wallet automation
Source: https://docs.privy.io/api-reference/wallet-automations/get

get /v1/wallet_automations/{automation_id}
Get a wallet automation by ID.





# Get wallet action by external ID
Source: https://docs.privy.io/api-reference/wallets/actions/external-id

get /v1/actions
Look up a wallet action by `reference_id` across every wallet in the app. Returns an empty list if no action matches. Use `?include=steps` to include step-level details.

Use this endpoint to look up a wallet action by a developer-provided `reference_id`. This is useful for
reconciling actions initiated via [transfer](/api-reference/wallets/transfer/index),
[swap](/api-reference/wallets/swap/quote) or [earn](/api-reference/wallets/earn/deposit) with your internal records.

Unlike [get wallet action](/api-reference/wallets/actions/get) and
[list all wallet actions](/api-reference/wallets/actions/list), this endpoint searches across every wallet in
your app, so you do not need to know which wallet performed the action.

<Tip>
  To set a `reference_id` on a wallet action, pass it in the request body when creating the action.
  The `reference_id` must be unique per app and can be up to 64 characters. See [Set a reference
  ID](/wallets/actions/reference-id) for examples.
</Tip>

If no action matches the given `reference_id`, the endpoint returns `200` with an empty list rather than a
`404`. Pass `?include=steps` to expand step-level details in the response.




# Get wallet action
Source: https://docs.privy.io/api-reference/wallets/actions/get

get /v1/wallets/{wallet_id}/actions/{action_id}
Get the current status of a wallet action by its ID.





# Create wallets in batch
Source: https://docs.privy.io/api-reference/wallets/batch-create

post /v1/wallets/batch
Creates multiple wallets in a single request.

### Batch behavior

This endpoint creates multiple wallets in a single request. Each wallet creation is processed independently, so a failure for one wallet does not affect the others.

If the request body is valid, the endpoint returns HTTP 200 with a `results` array containing the success or failure status for each wallet. Request-level errors (invalid body, authentication failure, rate limiting) return standard HTTP error codes before any wallets are processed.




# Create wallet
Source: https://docs.privy.io/api-reference/wallets/create

post /v1/wallets
Creates a new wallet on the requested chain and for the requested owner.

<Tip>
  Prior to creating a wallet, we strongly recommend you learn about wallet
  [controls](/controls/overview) and [policies](/controls/policies/overview) to understand the right
  configuration for your wallets.
</Tip>

### SDK methods

Learn more about creating wallets using our SDKs [here](/wallets/wallets/create/create-a-wallet).

<Warning>
  **Idempotency on errors:** On 4xx or 5xx, Privy caches the response and replays it for the same
  key. Generate a new key to retry after a server error. Policy violations are an exception and
  allow same-key retries.
</Warning>




# Export wallet
Source: https://docs.privy.io/api-reference/wallets/export

post /v1/wallets/{wallet_id}/export
Export a wallet's private key.

### SDK methods

Learn more about exporting wallets using our SDKs [here](/wallets/wallets/export).

***

This endpoint exports a wallet's private key using Hybrid Public Key Encryption (HPKE). The following HPKE configuration is supported:

* KEM (Key Encapsulation Mechanism): DHKEM\_P256\_HKDF\_SHA256
* KDF (Key Derivation Function): HKDF\_SHA256
* AEAD (Authenticated Encryption with Associated Data): CHACHA20\_POLY1305
* Mode: BASE




# Get wallet
Source: https://docs.privy.io/api-reference/wallets/get

get /v1/wallets/{wallet_id}
Get a wallet by wallet ID.

### SDK methods

Learn more about getting wallets using our SDKs [here](/wallets/wallets/get-a-wallet/get-wallet-by-id).




# Get wallets
Source: https://docs.privy.io/api-reference/wallets/get-all

get /v1/wallets
Get all wallets in your app.

### SDK methods

Learn more about getting wallets using our SDKs [here](/wallets/wallets/get-a-wallet/get-all-wallets).




# Get wallet by address
Source: https://docs.privy.io/api-reference/wallets/get-by-address

post /v1/wallets/address
Look up a wallet by its blockchain address. Returns the wallet object if found.





# User wallet created
Source: https://docs.privy.io/api-reference/webhooks/user/wallet_created

webhook user.wallet_created
Fired when an embedded wallet is created for a user.





# Wallet recovered
Source: https://docs.privy.io/api-reference/webhooks/wallet/recovered

webhook wallet.recovered
Fired when a user recovers their embedded wallet.





# Wallet recovery setup
Source: https://docs.privy.io/api-reference/webhooks/wallet/recovery_setup

webhook wallet.recovery_setup
Fired when a user sets up recovery for their embedded wallet.





# Automatic wallet creation
Source: https://docs.privy.io/basics/react-native/advanced/automatic-wallet-creation



If your app uses embedded wallets, you can configure Privy to create wallets **automatically** for your users as part of their **login** flow.

<Tabs>
  <Tab title="Ethereum">
    To configure Privy to automatically create embedded wallets for your user when they login, **set the `config.embedded.solana.createOnLogin`** property of your `PrivyProvider`:

    ```tsx theme={"system"}
    <PrivyProvider
        appId="your-privy-app-id"
        config={{
            embedded: {
                ethereum: {
                    createOnLogin: 'users-without-wallets',
                },
            },
        }}
    >
        {children}
    </PrivyProvider>
    ```

    <ParamField type="'all-users' | 'users-without-wallets' | 'off'">
      Determines when to create a wallet for the user.

      * `'all-users'`: Create a wallet for all users on login.
      * `'users-without-wallets'`: Create a wallet for users who do not have a wallet on login.
      * `'off'`: Do not create a wallet on login.
    </ParamField>
  </Tab>

  <Tab title="Solana">
    To configure Privy to automatically create embedded wallets for your user when they login, **set the `config.embedded.solana.createOnLogin`** property of your `PrivyProvider`:

    ```tsx theme={"system"}
    <PrivyProvider
        appId="your-privy-app-id"
        config={{
            embedded: {
                solana: {
                    createOnLogin: 'users-without-wallets',
                },
            },
        }}
    >
        {children}
    </PrivyProvider>
    ```

    <ParamField type="'all-users' | 'users-without-wallets' | 'off'">
      Determines when to create a wallet for the user.

      * `'all-users'`: Create a wallet for all users on login.
      * `'users-without-wallets'`: Create a wallet for users who do not have a wallet on login.
      * `'off'`: Do not create a wallet on login.
    </ParamField>
  </Tab>
</Tabs>




# Automatic wallet creation
Source: https://docs.privy.io/basics/react/advanced/automatic-wallet-creation



If your app uses embedded wallets, you can configure Privy to create wallets **automatically** for your users as part of their **login** flow.

<Warning>
  Automatic embedded wallet creation is currently not supported if your app uses Privy's whitelabel
  login interfaces. If this is the case for your app, you must [manually create embedded
  wallets](/wallets/wallets/create/create-a-wallet) for your users at the desired point in your
  onboarding flow.
</Warning>

<Note>
  Automatic wallet creation only applies to login via the Privy modal and not from whitelabel login
  methods. It does not trigger wallet creation for users who authenticate through direct login
  methods like loginWithCode, useLoginWithOAuth, or similar custom flows.
</Note>

<Tabs>
  <Tab title="Ethereum">
    To configure Privy to automatically create embedded wallets for your user when they login, **set the `config.embeddedWallets.ethereum.createOnLogin`** property of your `PrivyProvider`:

    ```tsx theme={"system"}
    <PrivyProvider
        appId="your-privy-app-id"
        config={{
            embeddedWallets: {
                ethereum: {
                    createOnLogin: "users-without-wallets",
                },
            },
        }}
    >
        {children}
    </PrivyProvider>
    ```

    <ParamField type="'all-users' | 'users-without-wallets' | 'off'">
      Determines when to create a wallet for the user.

      * `'all-users'`: Create a wallet for all users on login.
      * `'users-without-wallets'`: Create a wallet for users who do not have a wallet on login.
      * `'off'`: Do not create a wallet on login.
    </ParamField>
  </Tab>

  <Tab title="Solana">
    To configure Privy to automatically create embedded wallets for your user when they login, **set the `config.embeddedWallets.solana.createOnLogin`** property of your `PrivyProvider`:

    ```tsx theme={"system"}
    <PrivyProvider
        appId="your-privy-app-id"
        config={{
            embeddedWallets: {
                solana: {
                    createOnLogin: 'users-without-wallets',
                },
            },
        }}
    >
        {children}
    </PrivyProvider>
    ```

    <ParamField type="'all-users' | 'users-without-wallets' | 'off'">
      Determines when to create a wallet for the user.

      * `'all-users'`: Create a wallet for all users on login.
      * `'users-without-wallets'`: Create a wallet for users who do not have a wallet on login.
      * `'off'`: Do not create a wallet on login.
    </ParamField>
  </Tab>

  <Tab title="Ethereum & Solana">
    To configure Privy to automatically create embedded wallets for your user when they login, **set the `config.embeddedWallets.ethereum.createOnLogin`** and `config.embeddedWallets.solana.createOnLogin` properties of your `PrivyProvider`:

    ```tsx theme={"system"}
    <PrivyProvider
        appId="your-privy-app-id"
        config={{
            embeddedWallets: {
                ethereum: {
                    createOnLogin: 'users-without-wallets',
                },
                solana: {
                    createOnLogin: 'users-without-wallets',
                },
            },
        }}
    >
        {children}
    </PrivyProvider>
    ```
  </Tab>
</Tabs>




# Embedded wallets
Source: https://docs.privy.io/basics/troubleshooting/troubleshooting-embedded-wallets



**If you're running into issues with creating and using embedded wallets in your app, check out some common errors below, and how to resolve them.**

## Embedded wallets created on `localhost`, but not on deployment

If you are able to successfully create embedded wallets for your users on **`localhost`**, but not in a deployed environment, **double-check that the protocol for your deployment URL is `https://` (secure), and *not* `http://`**. Privy embedded wallets use the browser's native [WebCrypto API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API), which is only available in secure contexts like **`https://`**.

**In kind, you *must* use a secure context (`https://`) for your deployment.** Embedded wallets will *not* be created or work in insecure contexts like **`http://`**, except **`localhost`**, which is a special case and treated by the browser as a secure context.

## Access to the Base RPC URL has been blocked by CORS

If you're using embedded wallets on Base or Base Goerli, and see the following error:

```
Access to fetch at 'https://base-mainnet.blastapi.io/insert-api-key' from origin 'insert-your-origin' has been blocked by CORS policy...
```

**This likely indicates that your IP address has been rate limited by the Blast RPC URL for making too many requests within a short time window.**

Though this may appear to be a CORS violation, the initial error sent by Blast should indicate this rate limit (with a 429 status code). Successive errors due to the rate limit may not include the required CORS headers, which is why the overall error message appears as a CORS violation.

**If you are seeing this issue, please try again shortly.** If it still does not resolve, please [reach out](https://privy.io/slack) and we can help debug!




# Taking actions with organization wallets
Source: https://docs.privy.io/organizations/actions/overview



Once your organizations have been set up with wallets, you can facilitate users taking actions with those wallets using **intents**.

## What are intents?

**Intents** are an abstraction in the Privy system for **asynchronous authorization.** With intents, your application expresses an intent to take an action (e.g. update a policy, send a transaction), and later appends [authorization signatures](/controls/overview) to the intent as users of your application approve the intent.

Once the approval threshold for the intent is met, the intent is automatically executed.

<Info>
  [Learn more about intents](/transaction-management/intents/overview) to familiarize yourself with
  how organizations can asynchronously approve actions.
</Info>

## Using intents

At a high-level, you can use intents to take actions with organization wallets as follows:

<Steps>
  <Step title="Create an intent for the action">
    To start, programmatically create an intent for the action the organization intends to take with the wallet. This may be a wallet update (e.g. updating a policy), a signature, or a transaction.
  </Step>

  <Step title="Authenticate users of the organization">
    Next, authenticate users of the organization who have been provisioned access to the wallet (via the default key quorum or other key quorums).

    If using your own authentication service, simply [retrieve a valid JWT](/authentication/user-authentication/jwt-based-auth/usage) for the authenticated user.

    If using Privy's authentication service, simply [log in the user](/authentication/user-authentication/privy-auth) with your configured login methods using Privy's client-side SDKs.
  </Step>

  <Step title="Authorize the intent with the authenticated user">
    Once the user is authenticated, have them authorize the intent by fetching a user signing key with their access token and signing the intent request with it.

    We strongly suggest using Privy's [client-side SDKs](/controls/authorization-keys/using-owners/sign/signing-on-the-client) or [server-side SDKs](/controls/authorization-keys/using-owners/sign/signing-on-the-server) to facilitate intent authorization with a user's access token.
  </Step>

  <Step title="Capture the result of intent execution">
    Once a sufficient threshold of users approves the intent (e.g. the threshold of the default key quorum), Privy will automatically execute the intent.

    You can consume the result of intent execution via Privy's [REST API](/api-reference/intents/get) or by subscribing to [intent webhooks](/api-reference/webhooks/intents/executed).
  </Step>
</Steps>

## Wallet actions: swaps, Spark transfers, webhooks

Condensed API reference. Sources: https://docs.privy.io/api-reference/wallets/swap/tokens, /wallets/spark/transfer-tokens, /webhooks/intents/authorized, /wallets/authenticate.

### Swap tokens in a wallet

`POST /v1/wallets/{wallet_id}/swap` — executes a token swap inside a wallet.

- Prerequisites: swaps enabled in the Privy Dashboard; gas sponsorship configured for the app.
- Privy automates token approvals and submission. The response is a wallet action starting in `pending` status; poll for confirmation.
- Idempotency: the endpoint returns `pending` immediately and replays the cached response for the same idempotency key. On a synchronous 5xx, Privy deletes the record so the same key retries fresh. Action outcomes (`rejected`, `failed`, `succeeded`) arrive via webhooks and polling. Policy violations always allow fresh retries.

### Spark transferTokens

`POST /v1/wallets/{wallet_id}/rpc` with `{"method": "transferTokens", "network": "MAINNET", "params": {"token_identifier": "btkn...", "token_amount": N, "receiver_spark_address": "spark1..."}}` — transfers Spark tokens (token addresses start with `btkn`). Same idempotency-on-errors contract as swaps: cached replay on 4xx/5xx, new key required to retry after a server error, policy violations excepted.

### Wallet authorization keys (advanced)

`POST /v1/wallets/authenticate` exchanges a user JWT for an ephemeral session key authorized to act on the user's wallets. The returned `authorization_key` is HPKE-encrypted ciphertext (DHKEM_P256_HKDF_SHA256 / HKDF_SHA256 / CHACHA20_POLY1305, mode BASE) and must be decrypted client-side. Prefer the SDKs, which manage these keys internally.

### intent.authorized webhook

Fired when a user authorizes (signs) an intent. Subscribe to track quorum progress on organization-wallet intents without polling.
