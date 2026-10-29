#!/usr/bin/env node
/**
 * mint_nft.mjs — Mint a Metaplex Core NFT. Browser-signing only.
 *
 * The agent builds the create-asset transaction and PARTIALLY signs it with
 * an ephemeral asset keypair (the NFT's own address — discarded after use).
 * The user signs as fee payer / owner in their own browser wallet and
 * broadcasts. The agent never holds the user's private key.
 *
 * Usage:
 *   node mint_nft.mjs \
 *     --name "My NFT" \
 *     --uri ipfs://<METADATA_CID> \
 *     --owner <USER_WALLET_PUBKEY> \
 *     [--payer <PAYER_PUBKEY, defaults to --owner>] \
 *     [--rpc https://api.mainnet-beta.solana.com] \
 *     [--collection <COLLECTION_ADDRESS>]
 *
 * Output (JSON): { ok, asset_address, partial_tx (base64), ... }
 *   partial_tx is signed by the ephemeral asset keypair ONLY.
 *   The user's wallet must add the fee-payer signature and broadcast.
 *
 * Prerequisites: npm install (see ../package.json)
 * Metadata: host image + metadata JSON on IPFS via Pinata first
 *   (see the pinata skill: bin/pinata_pin.py pin-file). The --uri must be
 *   the ipfs://<CID> form (permanent, gateway-agnostic).
 */
import { createUmi } from '@metaplex-foundation/umi-bundle-defaults';
import { publicKey, generateSigner, transactionBuilder, createNoopSigner, signerIdentity, signTransaction } from '@metaplex-foundation/umi';
import { createV1 } from '@metaplex-foundation/mpl-core';

function arg(name, def = null) {
  const i = process.argv.indexOf(name);
  return i === -1 ? def : process.argv[i + 1];
}

const name = arg('--name');
const uri = arg('--uri');
const ownerStr = arg('--owner');
const payerStr = arg('--payer', ownerStr);
const rpc = arg('--rpc', 'https://api.mainnet-beta.solana.com');
const collectionStr = arg('--collection', null);

if (!name || !uri || !ownerStr) {
  console.error('missing required args: --name, --uri, --owner');
  process.exit(2);
}
if (!uri.startsWith('ipfs://')) {
  console.error('refusing: --uri must be the ipfs://<CID> form (Pinata-hosted metadata)');
  process.exit(2);
}

const umi = createUmi(rpc);
// Noop identity: carries the user's pubkey for building, but can NEVER
// sign. Real signing happens in the user's browser wallet.
const owner = publicKey(ownerStr);
const payer = publicKey(payerStr);
umi.use(signerIdentity(createNoopSigner(payer)));

// Ephemeral asset keypair: its only job is to co-sign creation.
// It holds no funds and is discarded after the transaction is built.
const asset = generateSigner(umi);

const createIx = createV1(umi, {
  asset,
  name,
  uri,
  owner,
  payer,
  ...(collectionStr ? { collection: publicKey(collectionStr) } : {}),
});

let builder = transactionBuilder().add(createIx);
builder = await builder.setLatestBlockhash(umi);
const tx = await builder.build(umi);

// Partial-sign with the asset keypair only. Fee payer signature comes
// from the user's browser wallet.
const partiallySigned = await signTransaction(tx, [asset]);
const serialized = umi.transactions.serialize(partiallySigned);
const base64Tx = Buffer.from(serialized).toString('base64');

// The ephemeral secret is intentionally NOT printed or persisted.

console.log(JSON.stringify({
  ok: true,
  asset_address: asset.publicKey,
  owner: ownerStr,
  payer: payerStr,
  name,
  uri,
  partial_tx: base64Tx,
  signers_remaining: ['fee payer / owner: ' + payerStr],
  next: 'Have the user sign partial_tx in their browser wallet (fee payer) and broadcast. ' +
        'Verify with: fetchAsset(' + asset.publicKey + ').',
}, null, 2));
