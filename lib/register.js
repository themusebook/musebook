/**
 * lib/register.js — on-chain agent registration for the Musebook CLI.
 *
 * Uses the Metaplex Agent API (https://api.metaplex.com/v1/agents/mint),
 * which returns an UNSIGNED transaction. The CLI then:
 *   1. shows exactly what will be signed (asset, network, fee payer),
 *   2. gets explicit user approval,
 *   3. signs locally (ed25519) or via the Privy device session (sign only),
 *   4. submits through a Solana RPC and polls until finalized.
 *
 * Metadata is hosted on IPFS via Pinata (PINATA_JWT env) or supplied
 * directly with --metadata-uri. Standing rule: ipfs:// URIs only.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const sol = require("./solana");
const privy = require("./privy");
const wallets = require("./wallets");

const METAPLEX_API = "https://api.metaplex.com";
const PINATA_API = "https://api.pinata.cloud";

class RegisterError extends Error {}

function networkArgs(network) {
  const n = (network || "mainnet").toLowerCase();
  // Metaplex API network values: "solana-mainnet" | "solana-devnet"
  // (per @metaplex-foundation/mpl-agent-registry client).
  if (n === "mainnet" || n === "mainnet-beta" || n === "solana-mainnet") {
    return { metaplex: "solana-mainnet", rpc: sol.defaultRpc("mainnet"), label: "mainnet" };
  }
  if (n === "devnet" || n === "solana-devnet") return { metaplex: "solana-devnet", rpc: sol.defaultRpc("devnet"), label: "devnet" };
  throw new RegisterError(`unknown network '${network}' — use mainnet or devnet`);
}

async function pinataPinFile(jwt, filePath, name) {
  const data = fs.readFileSync(filePath);
  const form = new FormData();
  form.append("file", new Blob([data]), path.basename(filePath));
  form.append("pinataMetadata", JSON.stringify({ name }));
  const res = await fetch(`${PINATA_API}/pinning/pinFileToIPFS`, {
    method: "POST",
    headers: { Authorization: `Bearer ${jwt}` },
    body: form,
  });
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    throw new RegisterError(`Pinata pin failed: HTTP ${res.status}: ${text.slice(0, 200)}`);
  }
  if (!res.ok || !body.IpfsHash) throw new RegisterError(`Pinata pin failed: ${body.error || text.slice(0, 200)}`);
  return body.IpfsHash;
}

function buildMetadataDoc({ name, description, imageUri, assetAddress }) {
  return {
    type: "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
    name,
    description: description || `${name} — a Solana AI agent registered via the Musebook CLI.`,
    image: imageUri || undefined,
    services: [],
    active: true,
    registrations: assetAddress
      ? [{ agentId: assetAddress, agentRegistry: "solana:101:metaplex" }]
      : [],
    supportedTrust: ["reputation"],
  };
}

async function resolveMetadataUri(args) {
  if (args.flags["metadata-uri"]) {
    const uri = args.flags["metadata-uri"];
    // Standing rule: metadata must live on IPFS. Enforce it.
    if (!uri.startsWith("ipfs://") || uri.length < 10) {
      throw new RegisterError(
        `refusing --metadata-uri "${uri.slice(0, 60)}": metadata must be an ipfs:// URI.\n` +
          "Host your ERC-8004 metadata JSON on IPFS, or set PINATA_JWT and I'll pin it for you."
      );
    }
    return { uri, pinned: false };
  }
  const jwt = process.env.PINATA_JWT;
  if (!jwt) {
    throw new RegisterError(
      "no --metadata-uri given and PINATA_JWT is not set.\n" +
        "Either host your ERC-8004 metadata JSON and pass --metadata-uri <ipfs://...>, " +
        "or set PINATA_JWT (transient env var) and I'll pin it for you."
    );
  }
  // Optional image first so its ipfs:// URI lands in the metadata.
  let imageUri = null;
  if (args.flags.image) {
    const cid = await pinataPinFile(jwt, args.flags.image, `${args.flags.name || "agent"}-image`);
    imageUri = `ipfs://${cid}`;
    console.log(`image pinned: ${imageUri}`);
  }
  const doc = buildMetadataDoc({
    name: args.flags.name,
    description: args.flags.description,
    imageUri,
    assetAddress: null,
  });
  const tmp = path.join(require("os").tmpdir(), `musebook-agent-metadata-${Date.now()}.json`);
  fs.writeFileSync(tmp, JSON.stringify(doc, null, 2));
  try {
    const cid = await pinataPinFile(jwt, tmp, `${args.flags.name || "agent"}-metadata`);
    return { uri: `ipfs://${cid}`, pinned: true };
  } finally {
    try { fs.unlinkSync(tmp); } catch {}
  }
}

/** Parse --wallet into { kind: 'local'|'privy', id }. */
function parseWalletRef(ref) {
  if (!ref) throw new RegisterError("register-agent needs --wallet <local:NAME|privy:WALLET_ID>");
  const m = /^(\w+):(.+)$/.exec(ref);
  if (!m) throw new RegisterError(`bad --wallet '${ref}' — use local:NAME or privy:WALLET_ID`);
  const kind = m[1].toLowerCase();
  if (kind !== "local" && kind !== "privy") throw new RegisterError(`bad --wallet kind '${m[1]}' — use local: or privy:`);
  return { kind, id: m[2] };
}

async function prompt(question) {
  const rl = require("readline").createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(question, (a) => { rl.close(); resolve(a); }));
}

async function registerAgent(args) {
  const name = args.flags.name || args._[0];
  if (!name || name.length < 1 || name.length > 64) {
    throw new RegisterError("register-agent needs a name (1–64 chars): musebook register-agent --name <name> --wallet <ref>");
  }
  const net = networkArgs(args.flags.network);
  const rpcUrl = args.flags.rpc || net.rpc;
  const walletRef = parseWalletRef(args.flags.wallet);

  // 1. Resolve the signing wallet's address (no secrets yet).
  let walletAddress;
  if (walletRef.kind === "local") {
    const found = wallets.listWallets().find((w) => w.name === walletRef.id);
    if (!found) throw new RegisterError(`local wallet '${walletRef.id}' not found — create it with \`musebook wallet create --name ${walletRef.id}\``);
    walletAddress = found.address;
  } else {
    const list = await privy.listWallets();
    const w = privy.findSolanaWallet(list, walletRef.id);
    walletAddress = w.address;
  }

  // 2. Metadata URI (Pinata or direct).
  console.log("resolving agent metadata...");
  const { uri: metadataUri, pinned } = await resolveMetadataUri(args);
  console.log(`metadata URI: ${metadataUri}${pinned ? " (pinned to IPFS just now)" : ""}`);

  // 3. Ask the Metaplex Agent API for the unsigned mint transaction.
  console.log("requesting unsigned mint transaction from the Metaplex Agent API...");
  let res;
  try {
    res = await fetch(`${METAPLEX_API}/v1/agents/mint`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        wallet: walletAddress,
        network: net.metaplex,
        name,
        uri: metadataUri,
        agentMetadata: {
          type: "agent",
          name,
          description: args.flags.description || `${name} — a Solana AI agent.`,
          services: [],
          registrations: [],
          supportedTrust: [],
        },
      }),
    });
  } catch (e) {
    throw new RegisterError(`Metaplex Agent API unreachable: ${e.message}`);
  }
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = null; }
  if (!res.ok || !body || !body.success) {
    throw new RegisterError(`Metaplex Agent API error: ${(body && (body.error || body.message)) || text.slice(0, 300)}`);
  }
  const unsignedB64 = body.tx;
  const assetAddress = body.assetAddress;
  if (!unsignedB64 || !assetAddress) throw new RegisterError("Metaplex API returned an unexpected response (no tx/assetAddress)");

  // 4. Inspect the transaction and show exactly what will be signed.
  const tx = sol.parseTransaction(unsignedB64);
  console.log();
  console.log("  Review the transaction to sign:");
  console.log(`    network      : ${net.label} (SVM)`);
  console.log(`    agent name   : ${name}`);
  console.log(`    asset        : ${assetAddress}`);
  console.log(`    fee payer    : ${tx.feePayer}`);
  console.log(`    metadata     : ${metadataUri}`);
  console.log(`    signers      : ${tx.numSignatures}`);
  if (tx.feePayer !== walletAddress) {
    throw new RegisterError(
      `fee payer mismatch: tx pays from ${tx.feePayer} but --wallet resolves to ${walletAddress}. Refusing to sign.`
    );
  }
  const lamports = await sol.getBalance(rpcUrl, walletAddress);
  console.log(`    wallet SOL   : ${(lamports / sol.LAMPORTS_PER_SOL).toFixed(6)}`);
  if (lamports < 0.02 * sol.LAMPORTS_PER_SOL) {
    console.log("    WARNING: balance looks low for mint + fees (~0.02 SOL recommended).");
  }

  if (!args.flags.yes) {
    const ok = await prompt("Sign and submit this agent registration? [y/N] ");
    if (!/^y(es)?$/i.test(ok.trim())) {
      console.log("aborted — nothing was signed or submitted.");
      return;
    }
  }

  // 5. Sign (never broadcast here).
  let signedB64;
  if (walletRef.kind === "local") {
    const { secretKey } = await wallets.loadSecretKey(walletRef.id);
    signedB64 = sol.partialSignTransaction(unsignedB64, secretKey, 0);
  } else {
    const data = await privy.signTransaction(walletRef.id, unsignedB64);
    // Privy returns the signature(s); splice them into the unsigned tx.
    const sigs = [];
    if (typeof data.signature === "string") sigs.push(data.signature);
    else if (Array.isArray(data.signatures)) sigs.push(...data.signatures);
    else if (typeof data.signedTransaction === "string") {
      signedB64 = data.signedTransaction;
    } else {
      throw new RegisterError(`unexpected signTransaction response: ${JSON.stringify(data).slice(0, 200)}`);
    }
    if (!signedB64) {
      // Splice the returned signature(s) into the unsigned transaction.
      const raw = Buffer.from(unsignedB64, "base64");
      let v = 0, shift = 0, i = 0;
      for (;;) {
        const b = raw[i++];
        v |= (b & 0x7f) << shift;
        if (!(b & 0x80)) break;
        shift += 7;
      }
      const sigLenBytes = i; // byte length of the compact-u16 signature count
      const out = Buffer.from(raw);
      sigs.slice(0, v).forEach((s58, idx) => {
        const sb = sol.b58decode(s58);
        if (sb.length !== 64) throw new RegisterError("bad signature length from Privy");
        sb.copy(out, sigLenBytes + idx * 64);
      });
      signedB64 = out.toString("base64");
    }
  }

  const signature = sol.txSignature(signedB64);
  console.log(`signed. tx signature: ${signature}`);

  // 6. Submit + confirm.
  console.log(`submitting to ${net.label}...`);
  const sent = await sol.sendTransaction(rpcUrl, signedB64);
  console.log(`submitted: ${sent}`);
  const conf = await sol.pollConfirmation(rpcUrl, sent);
  console.log(`confirmed: ${conf}`);

  // 7. Light on-chain verification: the asset account must exist now.
  const acct = await sol.rpcCall(rpcUrl, "getAccountInfo", [assetAddress, { encoding: "base64" }]);
  const scan = net.label === "devnet" ? "?cluster=devnet" : "";
  console.log();
  console.log(`🦞 agent "${name}" registered on Solana ${net.label}`);
  console.log(`  asset    : ${assetAddress}`);
  console.log(`  account  : ${acct && acct.value ? "exists on-chain ✓" : "NOT FOUND — investigate"}`);
  console.log(`  tx       : https://solscan.io/tx/${sent}${scan}`);
  console.log(`  asset    : https://solscan.io/account/${assetAddress}${scan}`);
  if (args.flags.json) console.log(JSON.stringify({ assetAddress, signature: sent, network: net.label }, null, 2));
}

module.exports = { RegisterError, registerAgent };
