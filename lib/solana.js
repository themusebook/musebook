/**
 * lib/solana.js — Solana (SVM) primitives in pure Node.js. No dependencies.
 *
 * - base58 encode/decode
 * - ed25519 keypair generation + signing (node:crypto)
 * - legacy transaction parsing + partial signing
 * - minimal JSON-RPC helpers (sendTransaction, getSignatureStatuses, getBalance)
 *
 * Solana only. There is no EVM support here and there never will be.
 */
"use strict";

const crypto = require("crypto");

// ---------------------------------------------------------------------------
// base58
// ---------------------------------------------------------------------------

const B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const B58_MAP = {};
for (let i = 0; i < B58_ALPHABET.length; i++) B58_MAP[B58_ALPHABET[i]] = i;

function b58encode(buf) {
  const bytes = Buffer.from(buf);
  let zeros = 0;
  while (zeros < bytes.length && bytes[zeros] === 0) zeros++;
  // base conversion
  const digits = [0];
  for (let i = zeros; i < bytes.length; i++) {
    let carry = bytes[i];
    for (let j = 0; j < digits.length; j++) {
      carry += digits[j] << 8;
      digits[j] = carry % 58;
      carry = (carry / 58) | 0;
    }
    while (carry > 0) {
      digits.push(carry % 58);
      carry = (carry / 58) | 0;
    }
  }
  let out = "";
  for (let i = 0; i < zeros; i++) out += "1";
  // Skip the digit emission when the value is zero (digits is all zeros):
  // the leading "1"s already encode those zero bytes.
  let nonZero = false;
  for (let i = 0; i < digits.length; i++) if (digits[i] !== 0) { nonZero = true; break; }
  if (nonZero) {
    for (let i = digits.length - 1; i >= 0; i--) out += B58_ALPHABET[digits[i]];
  }
  return out;
}

function b58decode(str) {
  if (typeof str !== "string" || !/^[1-9A-HJ-NP-Za-km-z]+$/.test(str)) {
    throw new Error("invalid base58 string");
  }
  let zeros = 0;
  while (zeros < str.length && str[zeros] === "1") zeros++;
  const bytes = [0];
  for (let i = zeros; i < str.length; i++) {
    let carry = B58_MAP[str[i]];
    for (let j = 0; j < bytes.length; j++) {
      carry += bytes[j] * 58;
      bytes[j] = carry & 0xff;
      carry >>= 8;
    }
    while (carry > 0) {
      bytes.push(carry & 0xff);
      carry >>= 8;
    }
  }
  // If the value is zero, `bytes` is just the [0] placeholder — drop it so
  // that "1" decodes to a single zero byte, not two.
  let valLen = bytes.length;
  let allZero = true;
  for (let i = 0; i < bytes.length; i++) if (bytes[i] !== 0) { allZero = false; break; }
  if (allZero) valLen = 0;
  const out = Buffer.alloc(zeros + valLen);
  for (let i = 0; i < valLen; i++) out[out.length - 1 - i] = bytes[i];
  return out;
}

// ---------------------------------------------------------------------------
// ed25519 (Solana keypairs)
// ---------------------------------------------------------------------------

/** Generate a fresh ed25519 keypair. Returns { publicKey: Buffer(32), secretKey: Buffer(64) }.
 *  secretKey follows the Solana convention: 32-byte seed || 32-byte public key. */
function generateKeypair() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const pub = publicKey.export({ format: "der", type: "spki" }).slice(-32);
  const seed = privateKey.export({ format: "der", type: "pkcs8" }).slice(-32);
  return { publicKey: pub, secretKey: Buffer.concat([seed, pub]) };
}

/** secretKey may be the 64-byte Solana form or the raw 32-byte seed. */
function ed25519Sign(message, secretKey) {
  const sk = Buffer.from(secretKey);
  if (sk.length !== 32 && sk.length !== 64) throw new Error("secret key must be 32 or 64 bytes");
  const seed = sk.slice(0, 32);
  const pkcs8 = Buffer.concat([
    Buffer.from("302e020100300506032b657004220420", "hex"),
    seed,
  ]);
  const key = crypto.createPrivateKey({ key: pkcs8, format: "der", type: "pkcs8" });
  return crypto.sign(null, Buffer.from(message), key); // 64 bytes
}

/** Verify a 64-byte ed25519 signature over message against a 32-byte public key.
 *  Returns true/false (never throws on a bad signature). */
function ed25519Verify(pubkey32, message, signature) {
  const pub = Buffer.from(pubkey32);
  if (pub.length !== 32) throw new Error("public key must be 32 bytes");
  const spki = crypto.createPublicKey({
    key: Buffer.concat([Buffer.from("302a300506032b6570032100", "hex"), pub]),
    format: "der",
    type: "spki",
  });
  try {
    return crypto.verify(null, Buffer.from(message), spki, Buffer.from(signature));
  } catch {
    return false;
  }
}

/** Solana address = base58(32-byte ed25519 public key). */
function pubkeyToAddress(pubkey32) {
  const b = Buffer.from(pubkey32);
  if (b.length !== 32) throw new Error("public key must be 32 bytes");
  return b58encode(b);
}

// ---------------------------------------------------------------------------
// legacy transactions
// ---------------------------------------------------------------------------

/** Read a compact-u16 (Solana shortvec) at offset. Returns [value, bytesRead]. */
function readCompactU16(buf, offset) {
  let value = 0;
  let shift = 0;
  let i = offset;
  for (;;) {
    if (i >= buf.length) throw new Error("truncated compact-u16");
    const b = buf[i++];
    value |= (b & 0x7f) << shift;
    if ((b & 0x80) === 0) break;
    shift += 7;
    if (shift > 21) throw new Error("compact-u16 overflow");
  }
  return [value, i - offset];
}

/**
 * Describe a base64 transaction for human review before signing.
 * Handles legacy and v0 messages. Returns:
 *   {
 *     version: "legacy" | "v0",
 *     feePayer: address, recentBlockhash: b58,
 *     numSignatures, numRequiredSignatures,
 *     accountKeys: [address...],  // static keys only
 *     lookupTables: [{ table, writableIndexes, readonlyIndexes }] | [],  // v0 only
 *     instructions: [{ programId, programIndex, accounts: [address|"lookup?..."], dataHex }],
 *     hasLookups: bool,
 *   }
 * For v0 transactions with address lookup tables, account indexes that refer
 * to lookup-loaded addresses are shown as "lookup:<table>:<index>" — the CLI
 * cannot resolve them offline, so review is explicit about the gap.
 */
function describeTransaction(b64) {
  const parsed = parseTransaction(b64);
  const m = parsed.messageBytes;
  let off = 0;
  let version = "legacy";
  let numRequiredSignatures, numReadonlySigned, numReadonlyUnsigned;
  // v0 messages start with a version byte (0x80 | version).
  if ((m[0] & 0x80) !== 0) {
    const v = m[0] & 0x7f;
    if (v !== 0) throw new Error(`unsupported message version: ${v}`);
    version = "v0";
    off = 1;
  }
  numRequiredSignatures = m[off];
  numReadonlySigned = m[off + 1];
  numReadonlyUnsigned = m[off + 2];
  off += 3;
  const [nKeys, kLen] = readCompactU16(m, off); off += kLen;
  const accountKeys = [];
  for (let i = 0; i < nKeys; i++) {
    accountKeys.push(pubkeyToAddress(m.slice(off, off + 32)));
    off += 32;
  }
  const recentBlockhash = b58encode(m.slice(off, off + 32));
  off += 32;

  // NOTE: in v0, compiled instructions come BEFORE the address table lookups.
  const [nIx, ixLen] = readCompactU16(m, off); off += ixLen;
  // We need the lookup tables to resolve dynamic addresses, so parse them
  // first (without resolving), then parse instructions.
  // Save the instruction section offset.
  const ixSectionOff = off;
  // Skip ahead: we need to parse instructions to know where lookups start...
  // Actually: instructions are self-delimiting, so parse them into a raw list
  // first, then parse lookups, then resolve addresses.
  const rawInstructions = [];
  {
    let o = off;
    for (let i = 0; i < nIx; i++) {
      const programIndex = m[o++];
      const [nAccts, aLen] = readCompactU16(m, o); o += aLen;
      const accountIndexes = [...m.slice(o, o + nAccts)]; o += nAccts;
      const [dLen, dLenBytes] = readCompactU16(m, o); o += dLenBytes;
      const dataHex = m.slice(o, o + dLen).toString("hex"); o += dLen;
      rawInstructions.push({ programIndex, accountIndexes, dataHex });
    }
    off = o;
  }

  // Address lookup tables (v0 only, after instructions).
  const lookupTables = [];
  if (version === "v0") {
    const [nTables, tLen] = readCompactU16(m, off); off += tLen;
    for (let i = 0; i < nTables; i++) {
      const table = pubkeyToAddress(m.slice(off, off + 32)); off += 32;
      const [nW, wLen] = readCompactU16(m, off); off += wLen;
      const writableIndexes = [...m.slice(off, off + nW)]; off += nW;
      const [nR, rLen] = readCompactU16(m, off); off += rLen;
      const readonlyIndexes = [...m.slice(off, off + nR)]; off += nR;
      lookupTables.push({ table, writableIndexes, readonlyIndexes });
    }
  } else {
    // Legacy: no lookup tables; nothing follows instructions.
  }

  const addrOf = (idx) => {
    if (idx < accountKeys.length) return accountKeys[idx];
    // v0 dynamic address: locate in lookup tables.
    let rel = idx - accountKeys.length;
    for (const t of lookupTables) {
      if (rel < t.writableIndexes.length) return `lookup:${t.table.slice(0, 8)}…:w${t.writableIndexes[rel]}`;
      rel -= t.writableIndexes.length;
      if (rel < t.readonlyIndexes.length) return `lookup:${t.table.slice(0, 8)}…:r${t.readonlyIndexes[rel]}`;
      rel -= t.readonlyIndexes.length;
    }
    return `unknown-account:${idx}`;
  };
  const instructions = rawInstructions.map((r) => ({
    programId: addrOf(r.programIndex),
    programIndex: r.programIndex,
    accounts: r.accountIndexes.map(addrOf),
    dataHex: r.dataHex,
  }));

  // Required signers = first numRequiredSignatures static keys.
  const signers = accountKeys.slice(0, numRequiredSignatures);

  return {
    version,
    feePayer: parsed.feePayer,
    recentBlockhash,
    numSignatures: parsed.numSignatures,
    numRequiredSignatures,
    numReadonlySigned,
    numReadonlyUnsigned,
    accountKeys,
    signers,
    lookupTables,
    hasLookups: lookupTables.length > 0,
    instructions,
  };
}

/**
 * Parse a base64 legacy transaction. Returns:
 *   { signatures: Buffer[], messageBytes: Buffer, numSignatures, feePayer: address }
 * The fee payer is the first account key in the message (index 0 of signers).
 */
function parseTransaction(b64) {
  const raw = Buffer.from(String(b64).trim(), "base64");
  if (raw.length < 65) throw new Error("transaction too short");
  const [nSigs, sigLenBytes] = readCompactU16(raw, 0);
  if (nSigs === 0 || nSigs > 64) throw new Error(`suspicious signature count: ${nSigs}`);
  const sigStart = sigLenBytes;
  const signatures = [];
  for (let i = 0; i < nSigs; i++) {
    signatures.push(raw.slice(sigStart + i * 64, sigStart + (i + 1) * 64));
  }
  const messageBytes = raw.slice(sigStart + nSigs * 64);
  if (messageBytes.length === 0) throw new Error("transaction has no message bytes");

  // fee payer = first account key in the message.
  // message header: 3 single bytes (numRequiredSignatures,
  // numReadonlySignedAccounts, numReadonlyUnsignedAccounts),
  // then compact-u16 account-key count, then the 32-byte keys.
  if (messageBytes.length < 4) throw new Error("transaction message too short");
  let off = 3;
  const [nKeys, kLen] = readCompactU16(messageBytes, off); off += kLen;
  if (nKeys === 0) throw new Error("transaction message has no account keys");
  const feePayer = pubkeyToAddress(messageBytes.slice(off, off + 32));

  return { signatures, messageBytes, numSignatures: nSigs, feePayer, raw };
}

/**
 * Sign a base64 legacy transaction's message bytes and place the signature
 * at `position` (default 0 = fee payer). Returns base64 of the signed tx.
 * Does NOT broadcast anything.
 */
function partialSignTransaction(b64, secretKey, position = 0) {
  const tx = parseTransaction(b64);
  if (position < 0 || position >= tx.numSignatures) {
    throw new Error(`signature position ${position} out of range (0..${tx.numSignatures - 1})`);
  }
  const sig = ed25519Sign(tx.messageBytes, secretKey);
  const out = Buffer.from(tx.raw);
  const [, sigLenBytes] = readCompactU16(out, 0);
  sig.copy(out, sigLenBytes + position * 64);
  return out.toString("base64");
}

/** Derive the Solana tx signature (base58 of the first signature) for display/polling. */
function txSignature(b64) {
  const tx = parseTransaction(b64);
  return b58encode(tx.signatures[0]);
}

// ---------------------------------------------------------------------------
// JSON-RPC
// ---------------------------------------------------------------------------

const DEFAULT_MAINNET_RPC = "https://api.mainnet-beta.solana.com";
const DEFAULT_DEVNET_RPC = "https://api.devnet.solana.com";

function defaultRpc(network) {
  if (process.env.SOLANA_RPC_URL) return process.env.SOLANA_RPC_URL;
  return network === "devnet" ? DEFAULT_DEVNET_RPC : DEFAULT_MAINNET_RPC;
}

async function rpcCall(rpcUrl, method, params) {
  let res;
  try {
    res = await fetch(rpcUrl, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
    });
  } catch (e) {
    throw new Error(`RPC network error (${method}): ${e.message}`);
  }
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`RPC bad response (${method}): HTTP ${res.status}`);
  }
  if (data.error) throw new Error(`RPC error (${method}): ${data.error.message || JSON.stringify(data.error)}`);
  return data.result;
}

/** Submit a signed base64 tx. Returns the signature (base58). No confirmation. */
async function sendTransaction(rpcUrl, signedB64) {
  return rpcCall(rpcUrl, "sendTransaction", [
    signedB64,
    { encoding: "base64", skipPreflight: false, preflightCommitment: "confirmed" },
  ]);
}

/** Poll getSignatureStatuses until finalized/confirmed or timeout. Returns the status string. */
async function pollConfirmation(rpcUrl, signature, { timeoutMs = 90000, intervalMs = 2000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const res = await rpcCall(rpcUrl, "getSignatureStatuses", [[signature], { searchTransactionHistory: true }]);
    const st = res && res.value && res.value[0];
    if (st && st.err) throw new Error(`transaction failed on-chain: ${JSON.stringify(st.err)}`);
    if (st && (st.confirmationStatus === "finalized" || st.confirmationStatus === "confirmed")) {
      return st.confirmationStatus;
    }
    if (Date.now() > deadline) throw new Error("confirmation timed out — check the signature on Solscan");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

async function getBalance(rpcUrl, address) {
  const { value } = await rpcCall(rpcUrl, "getBalance", [address]);
  return value; // lamports
}

module.exports = {
  b58encode,
  b58decode,
  generateKeypair,
  ed25519Sign,
  ed25519Verify,
  pubkeyToAddress,
  parseTransaction,
  describeTransaction,
  partialSignTransaction,
  txSignature,
  defaultRpc,
  rpcCall,
  sendTransaction,
  pollConfirmation,
  getBalance,
  LAMPORTS_PER_SOL: 1_000_000_000,
};
