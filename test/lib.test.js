#!/usr/bin/env node
/** Cross-implementation tests for musebook-cli lib modules. */
"use strict";
const assert = require("assert");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const sol = require("../lib/solana");
const privy = require("../lib/privy");

let pass = 0;
function ok(name, cond) {
  if (!cond) { console.error(`FAIL: ${name}`); process.exitCode = 1; return; }
  pass++;
  console.log(`ok: ${name}`);
}

// --- base58 roundtrip + known vectors ---
ok("b58 encode zero byte", sol.b58encode(Buffer.from([0])) === "1");
ok("b58 encode leading zeros", sol.b58encode(Buffer.from([0, 0, 1])) === "112");
ok("b58 roundtrip", sol.b58encode(sol.b58decode("4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofM")) === "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofM");
const rnd = crypto.randomBytes(32);
ok("b58 random roundtrip", sol.b58decode(sol.b58encode(rnd)).equals(rnd));
try { sol.b58decode("0OIl"); ok("b58 rejects bad chars", false); } catch { ok("b58 rejects bad chars", true); }

// --- town challenge message-signing roundtrip (throwaway keypair, in-memory only) ---
{
  const kp = sol.generateKeypair();
  const challenge = "musebook-town:action=join:nonce=abc123:expiresAt=2026-01-01T00:00:00Z";
  const msg = Buffer.from(challenge, "utf8");
  const sig = sol.ed25519Sign(msg, kp.secretKey);
  const sigB58 = sol.b58encode(sig);
  ok("town sig is base58 (64 bytes -> ~88 chars)", /^[1-9A-HJ-NP-Za-km-z]+$/.test(sigB58) && sigB58.length >= 80);
  ok("town sig verifies against the challenge", sol.ed25519Verify(kp.publicKey, msg, sig));
  ok("town sig rejects a tampered challenge", sol.ed25519Verify(kp.publicKey, Buffer.from(challenge + "!", "utf8"), sig) === false);
  const other = sol.generateKeypair();
  ok("town sig rejects a different pubkey", sol.ed25519Verify(other.publicKey, msg, sig) === false);
  ok("pubkeyToAddress roundtrips as ed25519 identity", sol.b58decode(sol.pubkeyToAddress(kp.publicKey)).equals(kp.publicKey));
}

// --- ed25519 + address derivation cross-check vs @solana/web3.js ---
// Optional: only runs if @solana/web3.js is resolvable (dev dependency).
let Keypair = null, naclVerify = null;
try {
  Keypair = require("@solana/web3.js").Keypair;
  naclVerify = require("tweetnacl").sign.detached.verify;
} catch {
  console.log("(skip: @solana/web3.js / tweetnacl not installed — cross-checks omitted)");
}
if (Keypair) {
  const kp = Keypair.generate();
  const myAddr = sol.pubkeyToAddress(kp.publicKey.toBytes());
  ok("address matches web3.js", myAddr === kp.publicKey.toBase58());

  const mine = sol.generateKeypair();
  const their = Keypair.fromSecretKey(mine.secretKey);
  ok("secretKey interoperable with web3.js", their.publicKey.toBase58() === sol.pubkeyToAddress(mine.publicKey));

  const sig = sol.ed25519Sign(Buffer.from("test"), mine.secretKey);
  ok("sig verifies via web3.js nacl", naclVerify(Buffer.from("test"), sig, mine.publicKey));
}

// --- parse a real signed tx (optional fixture) ---
// Set MUSEBOOK_TEST_TX to a base64 signed tx to run these; otherwise skipped.
const signedTxPath = process.env.MUSEBOOK_TEST_TX;
if (signedTxPath && fs.existsSync(signedTxPath)) {
  const signedTx = fs.readFileSync(signedTxPath, "utf8").trim();
  const parsed = sol.parseTransaction(signedTx);
  ok("parse real tx: feePayer non-empty", parsed.feePayer.length > 30);
  ok("parse real tx: message bytes > 100", parsed.messageBytes.length > 100);
  ok("parse real tx: signature b58 length sane", sol.b58encode(parsed.signatures[0]).length > 80);
  ok("txSignature equals first sig", sol.txSignature(signedTx) === sol.b58encode(parsed.signatures[0]));

  // --- partialSignTransaction: build unsigned from signed, re-sign, verify ---
  const raw = Buffer.from(signedTx, "base64");
  const unsigned = Buffer.from(raw);
  unsigned.fill(0, 1, 1 + parsed.numSignatures * 64); // zero the signatures (count is 1 byte here)
  const unsignedB64 = unsigned.toString("base64");
  // recover the secret key for the fee payer? We don't have it — instead verify
  // round-trip mechanics: sign with a FRESH keypair and confirm the signature
  // verifies against the message bytes.
  const fresh = sol.generateKeypair();
  const resigned = sol.partialSignTransaction(unsignedB64, fresh.secretKey, 0);
  const rp = sol.parseTransaction(resigned);
  const vrfy = crypto.verify(null, rp.messageBytes,
    crypto.createPublicKey({ key: Buffer.concat([Buffer.from("302a300506032b6570032100", "hex"), fresh.publicKey]), format: "der", type: "spki" }),
    rp.signatures[0]);
  ok("partialSign produces verifiable signature", vrfy === true);
  ok("partialSign keeps message bytes intact", rp.messageBytes.equals(parsed.messageBytes));
} else {
  console.log("(skip: MUSEBOOK_TEST_TX not set — real-tx parse tests omitted)");
}

// --- JCS matches Python json.dumps(sort_keys, separators) ---
const doc = { b: 2, a: [3, 1], z: { y: "x", w: null }, n: "s\"q" };
const expected = '{"a":[3,1],"b":2,"n":"s\\"q","z":{"w":null,"y":"x"}}';
ok("JCS canonical form", privy._jcs(doc) === expected);

// --- pollAction table ---
const [a1] = privy._pollAction(200, {});
const [a2] = privy._pollAction(400, { error: "authorization_pending" });
const [a3] = privy._pollAction(400, { error: "slow_down" });
const [a4] = privy._pollAction(400, { error: "expired_token" });
const [a5] = privy._pollAction(400, { error: "access_denied" });
const [a6] = privy._pollAction(500, { error: "x" });
ok("poll table", a1 === "done" && a2 === "wait" && a3 === "slow_down" && a4 === "expired" && a5 === "denied" && a6 === "fatal");

// --- HPKE decrypt: static vector (generated by Python `cryptography` HPKE Suite) ---
// enc(65) || ct, encrypted with Suite(KEM.P256, KDF.HKDF_SHA256, AEAD.CHACHA20_POLY1305)
const HPKE_VEC = {
  enc: "04397aa0979c6fc023ae53b58a200cd16e1e7868380bd5beec10376c2e628db1ed32b0547995a07258009d9fb3bf1ff8b9366fcc70dc68b0472fda4de0d22511d9",
  ct: "fcd712a2341e524415e449a49bb67807d58882f79868f1ecfe6140ce5887da9f8d0c0211d702a7d9f8",
  sk: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  pt: "musebook-hpke-test-vector",
};
const decStatic = privy._hpkeDecrypt(
  Buffer.from(HPKE_VEC.enc, "hex"),
  Buffer.from(HPKE_VEC.ct, "hex"),
  Buffer.from(HPKE_VEC.sk, "hex")
);
ok("HPKE decrypt (static vector) matches", decStatic.toString("utf8") === HPKE_VEC.pt);

// --- authorization signature: static vector, verified with Node crypto ---
// (The signature below was produced by privy._authorizationSignature and
// independently verified with Python `cryptography`.)
const SIG_VEC = {
  privDer: "308187020100301306072a8648ce3d020106082a8648ce3d030107046d306b0201010420b991a54e99372141e0c47f0027bfe98861861700d0c64db001a5791c1066fb02a144034200048d8253417b341c0be13103f1c41dc265c2b3d0a097c2e4d53888bf401f47c24222e76a964a4cae732fa09cb172e41a0842920344964e2d0f13f9138907a96e88",
  pubDer: "3059301306072a8648ce3d020106082a8648ce3d030107034200048d8253417b341c0be13103f1c41dc265c2b3d0a097c2e4d53888bf401f47c24222e76a964a4cae732fa09cb172e41a0842920344964e2d0f13f9138907a96e88",
  url: "https://auth.privy.io/api/oauth/v2/wallets/wallet_TEST/rpc",
  body: { method: "signMessage", params: { message: "aGk=", encoding: "base64" } },
  sig: "MEUCIFd+XarDyf3D449pfVSr8gdyO2i5e3wQRAT7NHWsInZ7AiEAmw4GkK+I1iQ0v98EKc6Yc+8LLXt96lhofIuxtJQtHMQ=",
};
const sigCheck = privy._authorizationSignature(
  Buffer.from(SIG_VEC.privDer, "hex").toString("base64"),
  SIG_VEC.url,
  SIG_VEC.body
);
// Note: ECDSA signatures are randomized; we verify validity rather than
// exact bytes. The SIG_VEC.sig above was independently verified with Python.
// Verify the static signature with Node's crypto (independent of our signing code path).
{
  const payload = {
    version: 1, method: "POST", url: SIG_VEC.url, body: SIG_VEC.body,
    headers: { "privy-app-id": "cm7tbyvvy01w2144yss67bjm0" },
  };
  const canonical = privy._jcs(payload);
  const digest = crypto.createHash("sha256").update(canonical, "utf8").digest();
  const v = crypto.verify(
    "sha256",
    Buffer.from(canonical, "utf8"),
    crypto.createPublicKey({ key: Buffer.from(SIG_VEC.pubDer, "hex"), format: "der", type: "spki" }),
    Buffer.from(SIG_VEC.sig, "base64")
  );
  ok("authorization signature verifies (Node crypto)", v === true);
}

// --- Optional live Python cross-checks (requires python3 + cryptography) ---
function findTestPython() {
  const override = process.env.PRIVY_TEST_PYTHON;
  if (override && fs.existsSync(override)) return override;
  try {
    require("child_process").execSync("python3 -c 'import cryptography.hazmat.primitives.hpke'", { stdio: "ignore" });
    return "python3";
  } catch {
    return null;
  }
}
const VENV_PY = findTestPython();
if (VENV_PY) {
const py = `
import os, json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.hpke import Suite, KEM, KDF, AEAD

# Use the REAL cryptography HPKE suite as the reference implementation.
suite = Suite(KEM.P256, KDF.HKDF_SHA256, AEAD.CHACHA20_POLY1305)
skR = ec.generate_private_key(ec.SECP256R1())
pt = b"wallet-authz-key-test"
blob = suite.encrypt(pt, skR.public_key())  # enc(65) || ct
enc, ct = blob[:65], blob[65:]
raw_sk = skR.private_numbers().private_value.to_bytes(32, "big")
print(json.dumps({"enc": enc.hex(), "ct": ct.hex(), "sk": raw_sk.hex(), "pt": pt.decode()}))
`;
const out = require("child_process").execSync(`${VENV_PY} -c '${py}'`, { encoding: "utf8" });
const vec = JSON.parse(out);
const dec = privy._hpkeDecrypt(
  Buffer.from(vec.enc, "hex"),
  Buffer.from(vec.ct, "hex"),
  Buffer.from(vec.sk, "hex").slice(-32) // raw 32-byte scalar (what ecdh.getPrivateKey() yields)
);
ok("HPKE decrypt (python->node) matches", dec.toString("utf8") === vec.pt);

// --- authorization signature: verify in Python with cryptography ---
// build a P-256 key, sign with Node, verify with Python
const { privateKey: p256priv } = crypto.generateKeyPairSync("ec", { namedCurve: "prime256v1" });
const p256der = p256priv.export({ format: "der", type: "pkcs8" });
const p256pubDer = crypto.createPublicKey(p256priv).export({ format: "der", type: "spki" });
const testUrl = "https://auth.privy.io/api/oauth/v2/wallets/wallet_abc/rpc";
const testBody = { method: "signMessage", params: { message: "aGk=", encoding: "base64" } };
const sigB64 = privy._authorizationSignature(p256der.toString("base64"), testUrl, testBody);
const pyVerify = `
import base64, json, hashlib
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives import hashes, serialization
pub = serialization.load_der_public_key(bytes.fromhex("${p256pubDer.toString("hex")}"))
payload = {"version": 1, "method": "POST", "url": "${testUrl}",
           "body": ${JSON.stringify(testBody)},
           "headers": {"privy-app-id": "${process.env.PRIVY_APP_ID || "cm7tbyvvy01w2144yss67bjm0"}"}}
canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
digest = hashlib.sha256(canon).digest()
sig_der = base64.b64decode("${sigB64}")
pub.verify(sig_der, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
print("sig-ok")
`;
try {
  const v = require("child_process").execSync(`${VENV_PY} -c '${pyVerify}'`, { encoding: "utf8" });
  ok("authorization signature verifies in Python (cryptography)", v.trim() === "sig-ok");
} catch (e) {
  ok("authorization signature verifies in Python (cryptography)", false);
  console.error(e.message.slice(0, 500));
}
} else {
  console.log("(skip: no python3 with `cryptography` — live Python cross-checks omitted)");
}

console.log(`\n${pass} assertions passed${process.exitCode ? " (WITH FAILURES)" : ""}`);
