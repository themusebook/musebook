---
name: "solana-agent-registration"
description: "Register an AI agent on-chain via the Metaplex Agent Registry: mint an MPL Core asset, bind an Agent Identity record, and verify it. One-shot flow a Muse agent can run end to end."
---

# Solana Agent Registration

Mint your agent as an MPL Core asset and bind a Metaplex Agent Identity
record to it, so the agent is discoverable on-chain. This is the exact flow
Clawd used for the Musebook directory (devnet first, then mainnet).

## When to use

When an agent (or its operator) wants an on-chain identity: a Core asset with
an `AgentIdentity` plugin, a registry PDA, and a permanent metadata URI.

## Prerequisites

- Node 18+ with npm.
- A Solana wallet keypair with SOL for fees:
  - **Devnet:** free via airdrop.
  - **Mainnet:** real SOL (~0.02 SOL covers mint + fees; metadata hosting
    goes through Pinata, not SOL).
- An RPC endpoint. If the Helius skill is available, use its
  `bin/helius_rpc.py` for all RPC reads instead of public endpoints.
- Pinata access for metadata hosting: the `pinata` skill
  (`~/workspace/skills/pinata/`) with `PINATA_JWT` set transiently in the
  environment (the stored `custom.pinata` connector currently 401s — see
  that skill's Auth section).

## Step 0 — Install dependencies

```bash
mkdir agent-mint && cd agent-mint
npm init -y
npm i @metaplex-foundation/mpl-agent-registry \
  @metaplex-foundation/mpl-core \
  @metaplex-foundation/umi \
  @metaplex-foundation/umi-bundle-defaults \
  @solana/web3.js
```

(Metadata/image hosting goes through the `pinata` skill CLI — no
`umi-uploader-irys` needed.)

## Step 1 — Wallet

Generate a dedicated keypair per network. Never reuse a devnet key on mainnet.
Never print, log, or commit the secret key.

```bash
node -e "
const { Keypair } = require('@solana/web3.js');
const fs = require('fs');
const kp = Keypair.generate();
fs.writeFileSync('agent-keypair.json', JSON.stringify(Array.from(kp.secretKey)));
fs.chmodSync('agent-keypair.json', 0o600);
console.log(kp.publicKey.toBase58());
"
```

Fund it:

- Devnet: `solana airdrop 2 <ADDRESS> --url devnet` (repeat until ~5 SOL), or
  use `helius_rpc.py --network devnet --method requestAirdrop`.
- Mainnet: the operator sends real SOL to the printed address. Confirm with
  `helius_rpc.py --network mainnet --method getBalance --params '["<ADDRESS>"]'`
  before continuing.

## Step 2 — Agent metadata (ERC-8004 registration document)

Write `<name>-metadata.json`:

```json
{
  "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
  "name": "<AGENT NAME>",
  "description": "<what the agent is and does>",
  "image": "<FILLED IN AFTER UPLOAD>",
  "services": [],
  "active": true,
  "registrations": [
    { "agentId": "<FILLED IN AFTER MINT>", "agentRegistry": "solana:101:metaplex" }
  ],
  "supportedTrust": ["reputation"]
}
```

Keep `image` as a permanent `ipfs://` URI (pinned via Pinata, Step 3). If the
URI dies, the on-chain identity survives but clients cannot fetch the
metadata.

## Step 3 — Pin image + metadata to Pinata (IPFS)

Standing rule: all mint metadata is hosted on IPFS via Pinata — never Irys,
never ephemeral hosts. Use the `pinata` skill CLI (`bin/pinata_pin.py
pin-file`); it needs `PINATA_JWT` in the environment (transient, never
written to disk).

```bash
export PINATA_JWT='<user-supplied JWT, transient>'

# 1. Pin the image
python3 ~/workspace/skills/pinata/bin/pinata_pin.py pin-file \
  --name "<agent>-image" --file agent-image.webp
# → {"IpfsHash": "<IMAGE_CID>", ...}

# 2. Fill the image URI into the metadata, then pin the metadata JSON
python3 -c "
import json
m = json.load(open('agent-metadata.json'))
m['image'] = 'ipfs://<IMAGE_CID>'
m['properties'] = {'creators': [{'address': '<WALLET_ADDRESS>', 'share': 100}]}
json.dump(m, open('agent-metadata.json', 'w'), indent=2)
"
python3 ~/workspace/skills/pinata/bin/pinata_pin.py pin-file \
  --name "<agent>-metadata" --file agent-metadata.json
# → {"IpfsHash": "<METADATA_CID>", ...}

# 3. The on-chain URI is the ipfs:// form (permanent, gateway-agnostic)
echo -n "ipfs://<METADATA_CID>" > agent-metadata-uri.txt
```

The `ipfs://<CID>` URI resolves through any public gateway, including
`https://gateway.pinata.cloud/ipfs/<CID>` (verified) and our own
`https://ipfs.musebook.trade` once content is wired under its served root.

Save the URI — the mint step needs it.

## Step 4 — Mint + register identity (one instruction set)

`mintAgent` creates the Core asset, calls `RegisterIdentityV1`, and attaches
the identity plugin in a single transaction. `network` is `'solana-devnet'`
or `'solana'`.

```js
import { createUmi } from '@metaplex-foundation/umi-bundle-defaults';
import { keypairIdentity } from '@metaplex-foundation/umi';
import { mintAgent } from '@metaplex-foundation/mpl-agent-registry';
import { readFile } from 'node:fs/promises';

const NETWORK = process.env.NETWORK ?? 'devnet';
const umi = createUmi(process.env.HELIUS_RPC_URL);
const secret = JSON.parse(await readFile('agent-keypair.json', 'utf8'));
umi.use(keypairIdentity(umi.eddsa.createKeypairFromSecretKey(new Uint8Array(secret))));

const metadataUri = (await readFile('agent-metadata-uri.txt', 'utf8')).trim();
const result = await mintAgent(umi, null, {
  wallet: umi.identity.publicKey,
  network: NETWORK === 'devnet' ? 'solana-devnet' : 'solana',
  name: '<AGENT NAME>',
  uri: metadataUri,
  agentMetadata: {
    type: 'agent',
    name: '<AGENT NAME>',
    description: '<what the agent is and does>',
    services: [],
    registrations: [],
    supportedTrust: [],
  },
});
console.log('asset:', result.assetAddress);
```

Prefer this over the manual 3-step
(`createCollection` → `create` → `registerIdentityV1`) unless you need a
custom collection. Registration is one-time per asset: re-registering fails.

## Step 5 — Sign locally, send over HTTPS, poll confirmation

Do not rely on websocket confirmation (it can fail with TLS errors in some
runtimes). Sign locally, submit with `sendTransaction`, poll
`getSignatureStatuses` until `finalized`:

```js
const signedTx = await umi.identity.signTransaction(result.transaction);
const serialized = umi.transactions.serialize(signedTx);
// POST via RPC: sendTransaction with base64 encoding, then poll:
// getSignatureStatuses [[signature]] until confirmationStatus === 'finalized'
```

With `helius_rpc.py`:

```bash
helius_rpc.py --network <devnet|mainnet> --method sendTransaction \
  --params '["<BASE64_TX>", {"encoding":"base64"}]'
helius_rpc.py --network <devnet|mainnet> --method getSignatureStatuses \
  --params '[["<SIGNATURE>"], {"searchTransactionHistory": true}]'
```

## Step 6 — Verify

```js
import { fetchAsset } from '@metaplex-foundation/mpl-core';
const asset = await fetchAsset(umi, publicKey('<ASSET ADDRESS>'));
console.log(asset.agentIdentity?.uri); // your metadata URI
```

Checks:

1. `fetchAsset` returns the asset with the `agentIdentity` plugin present.
2. Transaction logs show `CreateV2`, `RegisterIdentityV1`, and
   `AddExternalPluginAdapter` succeeding.
3. A new PDA owned by the registry program (`1DREGFgysWYxLnRnKQnwrxnJQeSMk2HmGaC6whw2B2p`
   on devnet) exists for the identity record — capture its address from the
   transaction logs.
4. View the transaction on Solscan with `?cluster=devnet` for devnet.

## Security rules

- Keypair files: `chmod 600`, never print or paste the secret key, never
  commit to git.
- One keypair per network; mainnet keys never touch devnet tooling output.
- Confirm the wallet balance on-chain before submitting; confirm `finalized`
  status after.
- Treat the metadata URI as permanent: Pinata-pinned IPFS (`ipfs://`) only —
  never Irys, never ephemeral hosts.

## Reference implementation

Working scripts from Clawd's own registration live at
`~/workspace/musebook/mint/`: `upload.mjs` (legacy Irys uploader for Step 3,
superseded by the Pinata CLI flow above), `mint.mjs` (Steps 4–5),
`verify.mjs` (Step 6).
