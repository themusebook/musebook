# Privy Policies & Authorization

Authorization policies, key quorums, condition sets, approvals, intents, MFA, signers and owners. Source: https://docs.privy.io/llms-full.txt

# Authorization signatures
Source: https://docs.privy.io/api-reference/authorization-signatures

Securing Privy API requests with authorization signatures

## Overview

[Owners](/controls/overview) provide an additional layer of security for actions taken by your app’s wallets. This primitive helps ensure that only actions explicitly authorized by your server are executed on user wallets.

When you specify an owner of a resource, all requests to update that resource must be signed with the associated key (user, authorization key, or key quorum). Requests to take actions with a wallet must also be signed by the wallet’s owner. This security measure verifies that each request comes from your authorized backend systems and helps prevent unauthorized operations.

<Tip>
  Authorization signatures are an important security measure and we strongly recommend registering
  authorization keys for all production resources.
</Tip>

<Info>
  Learn more about [owners](/controls/authorization-keys/owners/overview) and [authorization
  signatures](/controls/authorization-keys/keys/overview).
</Info>

### When are they necessary?

Authorization signatures are necessary in the following cases.

#### Updating wallets and policies

All critical resources, such as wallets and policies, have an `owner_id` field, which indicates the authorization key or quorum whose signatures are required in order to modify the given resource.

This means, if the `owner_id` is set, authorization signatures are required for all `PATCH` and `DELETE` requests to the resource. This includes:

* `PATCH /v1/wallets/[wallet_id]`
* `PATCH /v1/policies/[policy_id]`
* `DELETE /v1/policies/[policy_id]`

Signatures from the wallet's owner are required to take actions on a wallet by default. If an `owner_id` is set, authorization signatures are required for:

* `POST /v1/wallets/<wallet_id>/rpc`

#### Executing actions with wallets

Executing actions with wallets requires authorization signature(s) from the wallet's owner, if the wallet has an owner. This includes:

* `POST /v1/wallets/[wallet_id]/rpc`

#### Updating key quorums

Though key quorums do not have owners, updating or deleting a key quorum requires a satisfying set of signatures from the *existing* key quorum that meet the authorization threshold. This includes:

* `PATCH /v1/key_quorums/[key_quorum_id]`
* `DELETE /v1/key_quorum/[key_quorum_id]`

Signatures from the wallet's owner are required to take actions on a wallet by default. If an `owner_id` is set, authorization signatures are required for:

## Usage

At a high-level, the flow of using authorization signatures is as follows:

<Steps>
  <Step title="Get your private keys">
    Get the private keys that you will use to sign your request. This might be retrieved from the
    private keys you saved locally (app owners and key quorum owners) or requested from the Privy
    API using a user JWT (user owners).
  </Step>

  <Step title="Construct your request">
    Construct the request that you intend to make to Privy. This might be updating or deleting
    wallets, updating or deleting policies, updating or deleting key quorums, or taking actions with
    wallets.
  </Step>

  <Step title="Sign the request">Format and sign the request with your private key(s).</Step>

  <Step title="Include the signature as a request header">
    Finally, when making your request to Privy, include the authorization signature(s) as a string
    in the `privy-authorization-signature` header.
  </Step>
</Steps>

### Getting authorization keys

To start, get the private keys for the authorization key(s) that owner your resource.

If the owner of your resource is an authorization key, get the private key(s) that you saved locally when creating your owner in the Privy API or Dashboard. Privy does not save these private key(s) and cannot help you recover them.

If the owner of your resource is a user, request a time-bound user key to take actions with or update the resource. Follow the guide below to learn how to request user keys given a user's access token.

<CardGroup>
  <Card title="Using user owners" href="/controls/authorization-keys/keys/create/user/overview">
    Request keys for user owners.
  </Card>
</CardGroup>

<CardGroup>
  <Card title="Get user keys" href="/controls/authorization-keys/keys/create/user/overview">
    Request a user key with a user's access token to sign requests to the Privy API.
  </Card>
</CardGroup>

### Signing requests

Next, sign the request with your authorization key(s). Make sure to correctly format your request before signing the request.

If the owner of your resource is a key quorum, make sure to sign the request with enough authorization keys to meet the authorization threshold.

Follow this guide for instructions on how to correctly sign your request:

<CardGroup>
  <Card title="Sign requests" href="/controls/authorization-keys/using-owners/sign">
    Learn how to sign requests to the Privy API.
  </Card>
</CardGroup>

### Setting required headers

Once you have collected your authorization signature(s), set the following header on your request to the Privy API.

<ParamField type="string">
  The authorization signature. If multiple signatures are required, include them as a
  comma-delimited string.
</ParamField>

<ParamField type="string">
  A Unix timestamp in milliseconds (e.g., `1773679531000`) indicating when the request expires.
  Privy rejects requests where this value is in the past, helping prevent replay attacks. This
  header is included in the [signature
  payload](/controls/authorization-keys/using-owners/sign/overview#signature-payload) and must match
  the value used when computing the authorization signature.
</ParamField>

<Tip>
  If you are using Privy's SDKs, the appropriate authorization signature and request expiry headers
  are added automatically to your requests.
</Tip>




# Add items to a condition set
Source: https://docs.privy.io/api-reference/condition-sets/condition-set-items/create

post /v1/condition_sets/{condition_set_id}/condition_set_items
Add new items to a condition set. Can add up to 100 items at once.





# Delete an item from a condition set
Source: https://docs.privy.io/api-reference/condition-sets/condition-set-items/delete

delete /v1/condition_sets/{condition_set_id}/condition_set_items/{condition_set_item_id}
Delete an item from a condition set by condition set ID and item ID.





# Get an item from a condition set
Source: https://docs.privy.io/api-reference/condition-sets/condition-set-items/get

get /v1/condition_sets/{condition_set_id}/condition_set_items/{condition_set_item_id}
Get an item from a condition set by condition set ID and item ID.





# Get all items from a condition set
Source: https://docs.privy.io/api-reference/condition-sets/condition-set-items/get-all

get /v1/condition_sets/{condition_set_id}/condition_set_items
Get all items in a condition set with pagination support.





# Update items in a condition set
Source: https://docs.privy.io/api-reference/condition-sets/condition-set-items/update

put /v1/condition_sets/{condition_set_id}/condition_set_items
Replace all items in a condition set by condition set ID. Can add up to 100 items at once.





# Create condition set
Source: https://docs.privy.io/api-reference/condition-sets/create

post /v1/condition_sets
Create a new condition set. You must provide either "owner" or "owner_id" (but not both) to specify ownership.





# Delete condition set
Source: https://docs.privy.io/api-reference/condition-sets/delete

delete /v1/condition_sets/{condition_set_id}
Delete a condition set by condition set ID.





# Get condition set
Source: https://docs.privy.io/api-reference/condition-sets/get

get /v1/condition_sets/{condition_set_id}
Get a condition set by condition set ID.





# Update condition set
Source: https://docs.privy.io/api-reference/condition-sets/update

patch /v1/condition_sets/{condition_set_id}
Update a condition set by condition set ID.





# Get intent
Source: https://docs.privy.io/api-reference/intents/get

get /v1/intents/{intent_id}
Retrieve an intent by ID. Returns its current status, authorization details, and execution result when applicable. Requests authenticated with an app secret can retrieve any intent for the app. Requests authenticated with a user token can retrieve only intents that the authenticated user created, must approve, or has signed. Unrelated intents return a 404 response.





# List intents
Source: https://docs.privy.io/api-reference/intents/list

get /v1/intents
List intents for an app. Returns a paginated list with each intent's current status and details. Requests authenticated with an app secret can retrieve all intents for the app. Requests authenticated with a user token return only intents that the authenticated user created, must approve, or has signed. Query parameters only narrow this scoped result set.





# Reject intent
Source: https://docs.privy.io/api-reference/intents/reject

post /v1/intents/{intent_id}/reject
Reject a pending intent, preventing it from being executed. Can be called by the intent creator (via user token) or with the app secret.





# Update key quorum
Source: https://docs.privy.io/api-reference/intents/update-key-quorum

patch /v1/intents/key_quorums/{key_quorum_id}
Create an intent to update a key quorum. The intent must be authorized by the key quorum members before it can be executed.





# Update policy
Source: https://docs.privy.io/api-reference/intents/update-policy

patch /v1/intents/policies/{policy_id}
Create an intent to update a policy. The intent must be authorized by the policy owner before it can be executed.





# Update policy rule
Source: https://docs.privy.io/api-reference/intents/update-rule

patch /v1/intents/policies/{policy_id}/rules/{rule_id}
Create an intent to update a rule on a policy. The intent must be authorized by the policy owner before it can be executed.





# Create key quorum
Source: https://docs.privy.io/api-reference/key-quorums/create

post /v1/key_quorums
Create a new key quorum.

### SDK methods

Learn more about creating key quorums using our SDKs [here](/controls/key-quorum/create).




# Delete key quorum
Source: https://docs.privy.io/api-reference/key-quorums/delete

delete /v1/key_quorums/{key_quorum_id}
Delete a key quorum by key quorum ID.





# Get key quorum
Source: https://docs.privy.io/api-reference/key-quorums/get

get /v1/key_quorums/{key_quorum_id}
Get a key quorum by ID.





# Update key quorum
Source: https://docs.privy.io/api-reference/key-quorums/update

patch /v1/key_quorums/{key_quorum_id}
Update a key quorum by key quorum ID.





# Create policy
Source: https://docs.privy.io/api-reference/policies/create

post /v1/policies
Create a new policy.

### SDK methods

Learn more about creating policies using our SDKs [here](/controls/policies/create-a-policy).




# Delete policy
Source: https://docs.privy.io/api-reference/policies/delete

delete /v1/policies/{policy_id}
Delete a policy by policy ID.





# Get policy
Source: https://docs.privy.io/api-reference/policies/get

get /v1/policies/{policy_id}
Get a policy by policy ID.

### SDK methods

Learn more about getting policies using our SDKs [here](/controls/policies/get-a-policy).




# Add a rule to a policy
Source: https://docs.privy.io/api-reference/policies/rules/create

post /v1/policies/{policy_id}/rules
Create a new rule for a policy.





# Delete a rule from a policy
Source: https://docs.privy.io/api-reference/policies/rules/delete

delete /v1/policies/{policy_id}/rules/{rule_id}
Delete a rule by policy ID and rule ID.





# Get a rule from a policy
Source: https://docs.privy.io/api-reference/policies/rules/get

get /v1/policies/{policy_id}/rules/{rule_id}
Get a rule by policy ID and rule ID.





# Update a rule in a policy
Source: https://docs.privy.io/api-reference/policies/rules/update

patch /v1/policies/{policy_id}/rules/{rule_id}
Update a rule by policy ID and rule ID.





# Update policy
Source: https://docs.privy.io/api-reference/policies/update

patch /v1/policies/{policy_id}
Update a policy by policy ID.

### SDK methods

Learn more about updating policies using our SDKs [here](/controls/policies/update-a-policy).




# Intent created
Source: https://docs.privy.io/api-reference/webhooks/intents/created

webhook intent.created
Fired when a new intent is created.





# Intent executed
Source: https://docs.privy.io/api-reference/webhooks/intents/executed

webhook intent.executed
Fired when an intent is successfully executed (2xx response from enclave).





# Intent failed
Source: https://docs.privy.io/api-reference/webhooks/intents/failed

webhook intent.failed
Fired when an intent execution fails (non-2xx response from enclave).





# Intent rejected
Source: https://docs.privy.io/api-reference/webhooks/intents/rejected

webhook intent.rejected
Fired when an intent is rejected.





# MFA disabled
Source: https://docs.privy.io/api-reference/webhooks/mfa/disabled

webhook mfa.disabled
Fired when a user disables multi-factor authentication.





# MFA enabled
Source: https://docs.privy.io/api-reference/webhooks/mfa/enabled

webhook mfa.enabled
Fired when a user enables multi-factor authentication.
