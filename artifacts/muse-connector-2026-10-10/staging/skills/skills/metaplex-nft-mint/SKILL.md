---
name: "metaplex-nft-mint"
description: "Mint NFTs on Solana with Metaplex Core. The agent builds the create-asset transaction and partially signs with an ephemeral asset keypair; the user signs as fee payer in their browser wallet. Metadata hosted on IPFS via Pinata."
---

# Metaplex NFT Mint

Mint a Metaplex Core NFT (the current Metaplex standard) with
**browser signing**: the agent builds, the user signs.

## Signing rule (non-negotiable)

- The agent builds the transaction and partially signs it with an **ephemeral
  asset keypair** (the NFT's own address — it holds no funds and is discarded
  after use).
- The **user signs as fee payer / owner in their own browser wallet**.
  The agent never holds the user's private key.
- Every mint needs the user's fresh approval of the exact terms: name, URI,
  owner, network (devnet vs mainnet).

## Step 0 — Install dependencies

```bash
cd ~/workspace/skills/metaplex-nft-mint
npm install
```

## Step 1 — Host metadata on IPFS (Pinata)

Standing policy: image + metadata JSON on IPFS via Pinata, never ephemeral
hosts. On-chain `uri` uses the `ipfs://<CID>` form.

```bash
export PINATA_JWT='<user-supplied JWT, transient>'

# 1. Pin the image
python3 ~/workspace/skills/pinata/bin/pinata_pin.py pin-file \
  --name "mynft-image" --file ./art.png
# → {"IpfsHash": "<IMAGE_CID>", ...}

# 2. Write metadata JSON pointing at the image, then pin it
python3 -c "
import json
m = {
  'name': 'My NFT',
  'description': '...',
  'image': 'ipfs://<IMAGE_CID>',
  'properties': {'creators': [{'address': '<OWNER_WALLET>', 'share': 100}]}
}
json.dump(m, open('metadata.json', 'w'), indent=2)
"
python3 ~/workspace/skills/pinata/bin/pinata_pin.py pin-file \
  --name "mynft-metadata" --file ./metadata.json
# → {"IpfsHash": "<METADATA_CID>", ...}
```

## Step 2 — Build the (partially-signed) mint transaction

```bash
node bin/mint_nft.mjs \
  --name "My NFT" \
  --uri ipfs://<METADATA_CID> \
  --owner <USER_WALLET_PUBKEY> \
  [--payer <PAYER_PUBKEY>] \
  [--rpc <RPC_URL>] \
  [--collection <CORE_COLLECTION_ADDRESS>]
```

Output is JSON: `asset_address` (the new NFT's address), `partial_tx`
(base64, signed by the ephemeral asset keypair only), and the remaining
required signer (the fee payer).

Cost: ~0.01–0.02 SOL on mainnet for rent + fees. Use devnet first
(`--rpc https://api.devnet.solana.com`) — metadata stays the same.

## Step 3 — User signs and broadcasts

Hand `partial_tx` to the user's browser wallet. Any wallet-adapter
`signTransaction` handles a partially-signed VersionedTransaction: the wallet
adds the fee-payer signature. Then either:

- the wallet broadcasts itself (preferred), or
- the wallet returns the fully-signed base64 and the agent broadcasts it
  via RPC `sendTransaction`.

## Step 4 — Verify

```js
import { fetchAsset } from '@metaplex-foundation/mpl-core';
const asset = await fetchAsset(umi, publicKey('<ASSET_ADDRESS>'));
console.log(asset.name, asset.uri, asset.owner);
```

The on-chain `uri` must equal the `ipfs://<CID>` you pinned. Resolve it
through any gateway to double-check the metadata renders.

## Notes

- For **agent** on-chain identity (MPL Core asset + Agent Identity plugin +
  registry record), use the `solana-agent-registration` skill instead — it is
  the same Core machinery with the identity plugin attached.
- For compressed NFTs (cNFTs, state-compressed, ~160x cheaper), see the
  `compressed-token` / `compressed-pda` skills.
- Never reuse an asset address. Each `--name`/`--uri` pair gets a fresh
  ephemeral keypair per run.
