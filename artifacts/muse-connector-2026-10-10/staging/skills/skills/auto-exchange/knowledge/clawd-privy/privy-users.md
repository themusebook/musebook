# Privy Users

Users API: create/get/update/delete users, linked accounts, custom metadata, identity tokens. Source: https://docs.privy.io/llms-full.txt

# Create user
Source: https://docs.privy.io/api-reference/users/create

post /v1/users
Create a new user with linked accounts. Optionally pre-generate embedded wallets for the user.

### SDK methods

Learn more about creating users using our SDKs [here](/user-management/migrating-users-to-privy/create-or-import-a-user).




# Add custom metadata
Source: https://docs.privy.io/api-reference/users/custom-metadata/create

post /v1/users/{user_id}/custom_metadata
Adds custom metadata to a user by user ID.

### SDK methods

Learn more about custom metadata using our SDKs [here](/user-management/users/custom-metadata).




# Update custom metadata
Source: https://docs.privy.io/api-reference/users/custom-metadata/update

patch /v1/users/{user_id}/custom_metadata
Partially updates custom metadata for a user by user ID. Only top-level keys provided in the request are updated; unspecified keys are preserved.

### SDK methods

Learn more about custom metadata using our SDKs [here](/user-management/users/custom-metadata).




# Delete user
Source: https://docs.privy.io/api-reference/users/delete

delete /v1/users/{user_id}
Delete a user by user ID.

### SDK methods

Learn more about deleting users using our SDKs [here](/user-management/users/managing-users/deleting-users).




# Get user by ID
Source: https://docs.privy.io/api-reference/users/get

get /v1/users/{user_id}
Get a user by user ID.

### SDK methods

Learn more about querying users using our SDKs [here](/user-management/users/managing-users/querying-users).

<Warning>
  This endpoint is heavily rate limited. If you're looking to get information about an authenticated
  user, consider using [identity tokens](/user-management/users/identity-tokens) as a more efficient
  way to access user data.
</Warning>




# Get users
Source: https://docs.privy.io/api-reference/users/get-all

get /v1/users
Get all users in your app.

### SDK methods

Learn more about querying users using our SDKs [here](/user-management/users/managing-users/querying-users).




# Get user by Discord username
Source: https://docs.privy.io/api-reference/users/get-by-discord-username

post /v1/users/discord/username
Looks up a user by their Discord username.





# Get user by email address
Source: https://docs.privy.io/api-reference/users/get-by-email-address

post /v1/users/email/address
Looks up a user by their email address.





# Get user by Farcaster ID
Source: https://docs.privy.io/api-reference/users/get-by-farcaster-id

post /v1/users/farcaster/fid
Looks up a user by their Farcaster ID.





# Get user by GitHub username
Source: https://docs.privy.io/api-reference/users/get-by-github-username

post /v1/users/github/username
Looks up a user by their Github username.





# Get user by Instagram username
Source: https://docs.privy.io/api-reference/users/get-by-instagram-username

post /v1/users/instagram/username
Looks up a user by their Instagram username.





# Get user by phone number
Source: https://docs.privy.io/api-reference/users/get-by-phone-number

post /v1/users/phone/number
Looks up a user by their phone number.





# Get user by Spotify subject
Source: https://docs.privy.io/api-reference/users/get-by-spotify-subject

post /v1/users/spotify/subject
Looks up a user by their Spotify subject (user ID).





# Get user by Telegram user ID
Source: https://docs.privy.io/api-reference/users/get-by-telegram-user-id

post /v1/users/telegram/telegram_user_id
Looks up a user by their Telegram user ID.





# Get user by Telegram username
Source: https://docs.privy.io/api-reference/users/get-by-telegram-username

post /v1/users/telegram/username
Looks up a user by their Telegram username.





# Get user by Twitch username
Source: https://docs.privy.io/api-reference/users/get-by-twitch-username

post /v1/users/twitch/username
Looks up a user by their Twitch username.





# Get user by Twitter subject
Source: https://docs.privy.io/api-reference/users/get-by-twitter-subject

post /v1/users/twitter/subject
Looks up a user by their Twitter subject.





# Get user by Twitter username
Source: https://docs.privy.io/api-reference/users/get-by-twitter-username

post /v1/users/twitter/username
Looks up a user by their Twitter username.





# Search users
Source: https://docs.privy.io/api-reference/users/search

post /v1/users/search
Search users by search term, emails, phone numbers, or wallet addresses.

### SDK methods

Learn more about querying users using our SDKs [here](/user-management/users/managing-users/querying-users).




# User created
Source: https://docs.privy.io/api-reference/webhooks/user/created

webhook user.created
Fired when a new user is created in your app.





# User deleted
Source: https://docs.privy.io/api-reference/webhooks/user/deleted

webhook user.deleted
Fired when a user is deleted from your app, for any reason (manual deletion or account merge).





# User linked account
Source: https://docs.privy.io/api-reference/webhooks/user/linked_account

webhook user.linked_account
Fired when a user links a new account (email, phone, wallet, social login, etc.) to their profile.





# User transferred account
Source: https://docs.privy.io/api-reference/webhooks/user/transferred_account

webhook user.transferred_account
Fired when an account is transferred from one user to another.





# User unlinked account
Source: https://docs.privy.io/api-reference/webhooks/user/unlinked_account

webhook user.unlinked_account
Fired when a user unlinks an account from their profile.





# User updated account
Source: https://docs.privy.io/api-reference/webhooks/user/updated_account

webhook user.updated_account
Fired when a user updates one of their linked accounts.
