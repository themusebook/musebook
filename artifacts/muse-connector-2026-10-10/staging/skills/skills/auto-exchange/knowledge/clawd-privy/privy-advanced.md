# Privy Advanced

Webhooks, x402, gas sponsorship, custom auth, allowlists, automations, onramps, swaps, security, migrations. Source: https://docs.privy.io/llms-full.txt

# Add to allowlist
Source: https://docs.privy.io/api-reference/apps/add-to-allowlist

post /v1/apps/{app_id}/allowlist
Add a new entry to the allowlist for an app. The allowlist must be enabled.

### SDK methods

Learn more about managing your allowlist using our SDKs [here](/user-management/users/managing-users/allowlist#adding-to-the-allow-list).




# List allowlist entries
Source: https://docs.privy.io/api-reference/apps/list-allowlist

get /v1/apps/{app_id}/allowlist
Get all allowlist entries for an app. Returns the list of users allowed to access the app when the allowlist is enabled.

### SDK methods

Learn more about managing your allowlist using our SDKs [here](/user-management/users/managing-users/allowlist#getting-the-allow-list).




# Remove from allowlist
Source: https://docs.privy.io/api-reference/apps/remove-from-allowlist

delete /v1/apps/{app_id}/allowlist
Remove an entry from the allowlist for an app. The allowlist must be enabled.

### SDK methods

Learn more about managing your allowlist using our SDKs [here](/user-management/users/managing-users/allowlist#removing-from-the-allow-list).




# Create fiat deposit account
Source: https://docs.privy.io/api-reference/fiat/deposit-accounts/create

post /v1/wallets/{wallet_id}/deposit_accounts/fiat
Creates a Bridge Virtual Account linked to a wallet. Fiat sent to the returned deposit instructions will be converted to the specified crypto asset and delivered to the wallet.





# Get fiat deposit account
Source: https://docs.privy.io/api-reference/fiat/deposit-accounts/get

get /v1/wallets/{wallet_id}/deposit_accounts/fiat/{deposit_account_id}
Returns a single fiat deposit account linked to a wallet.





# List fiat deposit accounts
Source: https://docs.privy.io/api-reference/fiat/deposit-accounts/list

get /v1/wallets/{wallet_id}/deposit_accounts/fiat
Returns a list of fiat deposit accounts linked to a wallet.





# Create external fiat account
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/create

post /v1/users/{user_id}/external_fiat_accounts
Creates an external fiat account linked to a user for use in offramp transfers.





# Delete external fiat account
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/delete

delete /v1/users/{user_id}/external_fiat_accounts/{account_id}
Deletes an external fiat account linked to a user.





# Get external fiat account
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/get

get /v1/users/{user_id}/external_fiat_accounts/{account_id}
Returns a single external fiat account linked to a user.





# List external fiat accounts
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/list

get /v1/users/{user_id}/external_fiat_accounts
Returns a list of external fiat accounts linked to a user.





# Create external fiat account
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/organizations/create

post /v1/organizations/{organization_id}/external_fiat_accounts
Creates an external fiat account linked to an organization for use in offramp transfers.





# Delete external fiat account
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/organizations/delete

delete /v1/organizations/{organization_id}/external_fiat_accounts/{account_id}
Deletes an external fiat account linked to an organization.





# Get external fiat account
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/organizations/get

get /v1/organizations/{organization_id}/external_fiat_accounts/{account_id}
Returns a single external fiat account linked to an organization.





# List external fiat accounts
Source: https://docs.privy.io/api-reference/fiat/external-fiat-accounts/organizations/list

get /v1/organizations/{organization_id}/external_fiat_accounts
Returns a list of external fiat accounts linked to an organization.





# Get KYB status
Source: https://docs.privy.io/api-reference/fiat/kyb/get

get /v1/organizations/{organization_id}/kyb
Returns KYB status for all providers the organization has initiated KYB with.





# Initiate KYB verification
Source: https://docs.privy.io/api-reference/fiat/kyb/links

post /v1/organizations/{organization_id}/kyb/links
Generates a hosted KYB link for the organization and returns the current KYB status snapshot.





# Submit KYB data
Source: https://docs.privy.io/api-reference/fiat/kyb/submit

post /v1/organizations/{organization_id}/kyb/submit
Submits KYB verification data for the organization. Safe to call more than once: the first call creates the provider customer and later calls update it, so a partial submission can be completed incrementally.





# Initiate KYB terms of service
Source: https://docs.privy.io/api-reference/fiat/kyb/tos

post /v1/organizations/{organization_id}/kyb/tos
Generates a Bridge terms-of-service acceptance link for the organization.





# Get KYC status
Source: https://docs.privy.io/api-reference/fiat/kyc-server/get

get /v1/users/{user_id}/kyc
Returns KYC status for all providers the user has initiated KYC with.





# Initiate KYC verification
Source: https://docs.privy.io/api-reference/fiat/kyc-server/links

post /v1/users/{user_id}/kyc/links
Generates a hosted KYC link for the user and returns the current KYC status snapshot.





# Submit KYC data
Source: https://docs.privy.io/api-reference/fiat/kyc-server/submit

post /v1/users/{user_id}/kyc/submit
Submits KYC verification data for the user. Safe to call more than once: the first call creates the provider customer and later calls update it, so a partial submission can be completed incrementally. The first submission must carry enough to begin verification — name, date of birth, residential address and at least one identifying document; later calls may send only the fields that change.





# Initiate KYC terms of service
Source: https://docs.privy.io/api-reference/fiat/kyc-server/tos

post /v1/users/{user_id}/kyc/tos
Generates a Bridge terms-of-service acceptance link for the user.





# Get user by custom auth ID
Source: https://docs.privy.io/api-reference/users/get-by-custom-auth

post /v1/users/custom_auth/id
Looks up a user by their custom auth ID.





# Attach wallet automations
Source: https://docs.privy.io/api-reference/wallet-automations/attach

post /v1/wallets/{wallet_id}/automations/attach
Attach one or more automations to a wallet.

<Warning>
  The wallet must be generated by Privy and never exported. Users cannot attach automations to
  imported or previously exported wallets.
</Warning>

Attaching an automation that is already attached updates its parameters and preserves its matching priority.




# Delete wallet automation
Source: https://docs.privy.io/api-reference/wallet-automations/delete

delete /v1/wallet_automations/{automation_id}
Delete a wallet automation and its wallet attachments.





# Detach wallet automations
Source: https://docs.privy.io/api-reference/wallet-automations/detach

post /v1/wallets/{wallet_id}/automations/detach
Detach one or more automations from a wallet.





# List wallet automations
Source: https://docs.privy.io/api-reference/wallet-automations/list

get /v1/wallet_automations
List wallet automations, optionally filtered by an attached wallet.





# List wallet automation executions
Source: https://docs.privy.io/api-reference/wallet-automations/list-executions

get /v1/wallet_automations/executions
List wallet automation executions, optionally filtered by wallet.





# Reindex wallet automations
Source: https://docs.privy.io/api-reference/wallet-automations/reindex

post /v1/wallet_automations/reindex
Recheck a wallet balance and recover a missed or failed automation execution.

Reindexing checks the asset's current wallet balance. It does not replay the original deposit amount.

See [recover a missed or failed deposit](/controls/automations/lifecycle#recover-a-missed-or-failed-deposit) for recovery behavior and result statuses.




# Update wallet automation
Source: https://docs.privy.io/api-reference/wallet-automations/update

patch /v1/wallet_automations/{automation_id}
Update, enable, or disable a wallet automation.





# Earn fee collect
Source: https://docs.privy.io/api-reference/wallets/earn/fees-collect

post /v1/wallets/{wallet_id}/earn/ethereum/fees/collect
Collect accumulated performance fees from an Aave vault.

<Tip>
  If your app has gas sponsorship configured, usage of the `/earn/ethereum/fees/collect` endpoint
  will be [gas-sponsored by default](/wallets/actions/overview#gas-management). There is no need to
  specify additional parameters for sponsorship.
</Tip>




# Get swap quote
Source: https://docs.privy.io/api-reference/wallets/swap/quote

post /v1/wallets/{wallet_id}/swap/quote
Get a price quote for swapping tokens within a wallet.

### Prerequisites

* Swaps must be [enabled in the Privy Dashboard](/wallets/actions/swap/setup)
* [Gas sponsorship](/wallets/gas-and-asset-management/gas/setup) must be configured for your app

***

<Tip>
  Swap quotes reflect real-time market conditions and can change quickly. Fetch a fresh quote before
  executing a swap to ensure your app displays accurate pricing.
</Tip>




# Gas sponsorship charge recorded
Source: https://docs.privy.io/api-reference/webhooks/usage/gas_sponsorship_recorded

webhook usage.gas_sponsorship.recorded
Fired when Privy records a sponsored-gas charge for a wallet action.





# Earn deposit created
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-deposit/created

webhook wallet_action.earn_deposit.created
Fired when a wallet action is created and execution has begun. The action is now pending.





# Earn deposit failed
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-deposit/failed

webhook wallet_action.earn_deposit.failed
Fired when a wallet action fails after at least one transaction was broadcast. There may be onchain state changes; inspect the steps for details.





# Earn deposit rejected
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-deposit/rejected

webhook wallet_action.earn_deposit.rejected
Fired when a wallet action fails before any onchain effects (e.g. policy rejection, simulation failure). Safe to retry.





# Earn deposit succeeded
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-deposit/succeeded

webhook wallet_action.earn_deposit.succeeded
Fired when all steps of a wallet action have been confirmed onchain. The action is complete.





# Earn fee collect created
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-fee-collect/created

webhook wallet_action.earn_fee_collect.created
Fired when a wallet action is created and execution has begun. The action is now pending.





# Earn fee collect failed
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-fee-collect/failed

webhook wallet_action.earn_fee_collect.failed
Fired when a wallet action fails after at least one transaction was broadcast. There may be onchain state changes; inspect the steps for details.





# Earn fee collect rejected
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-fee-collect/rejected

webhook wallet_action.earn_fee_collect.rejected
Fired when a wallet action fails before any onchain effects (e.g. policy rejection, simulation failure). Safe to retry.





# Earn fee collect succeeded
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-fee-collect/succeeded

webhook wallet_action.earn_fee_collect.succeeded
Fired when all steps of a wallet action have been confirmed onchain. The action is complete.





# Earn reward incentive claim created
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-incentive-claim/created

webhook wallet_action.earn_incentive_claim.created
Fired when a wallet action is created and execution has begun. The action is now pending.





# Earn reward incentive claim failed
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-incentive-claim/failed

webhook wallet_action.earn_incentive_claim.failed
Fired when a wallet action fails after at least one transaction was broadcast. There may be onchain state changes; inspect the steps for details.





# Earn reward incentive claim rejected
Source: https://docs.privy.io/api-reference/webhooks/wallet-action/earn-incentive-claim/rejected

webhook wallet_action.earn_incentive_claim.rejected
Fired when a wallet action fails before any onchain effects (e.g. policy rejection, simulation failure). Safe to retry.
