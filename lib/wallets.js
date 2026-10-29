/**
 * lib/wallets.js — local Solana keypairs for the Musebook CLI.
 *
 * `musebook wallet create` generates a real ed25519 keypair. The 64-byte
 * secret key is encrypted with AES-256-GCM under a key derived from a user
 * password (scrypt) and stored at ~/.config/musebook-cli/wallets/<name>.json
 * (0600). The password is never stored; it is prompted (no echo) on each use.
 *
 * This is the "actual wallet creation" path — self-custodied, no Privy
 * involved. Keep mainnet keys separate from devnet keys (use --network when
 * creating, stored as metadata only; the key itself is network-agnostic).
 */
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const readline = require("readline");
const sol = require("./solana");

const WALLETS_DIR = path.join(os.homedir(), ".config", "musebook-cli", "wallets");

class WalletError extends Error {}

function walletPath(name) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(name)) {
    throw new WalletError("wallet name must be 1-64 chars: letters, digits, _ or -");
  }
  return path.join(WALLETS_DIR, `${name}.json`);
}

function promptPassword(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const stdin = process.stdin;
    let muted = true;
    const onData = (ch) => {
      if (!muted) return;
      const s = ch.toString("utf8");
      if (s === "\r" || s === "\n" || s === "\u0004") return;
      // erase the typed char from the terminal
      process.stdout.write("\x1b[2K\x1b[200D" + question + "*".repeat(rl.line.length));
    };
    if (stdin.isTTY) {
      stdin.setRawMode(true);
      stdin.on("data", onData);
    }
    rl.question(question, (answer) => {
      if (stdin.isTTY) {
        stdin.setRawMode(false);
        stdin.removeListener("data", onData);
      }
      rl.close();
      process.stdout.write("\n");
      resolve(answer);
    });
  });
}

function deriveKey(password, salt) {
  return crypto.scryptSync(String(password), salt, 32, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
}

function encryptSecret(secretKey64, password) {
  const salt = crypto.randomBytes(16);
  const nonce = crypto.randomBytes(12);
  const key = deriveKey(password, salt);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, nonce);
  const ct = Buffer.concat([cipher.update(secretKey64), cipher.final()]);
  return {
    salt: salt.toString("base64"),
    nonce: nonce.toString("base64"),
    data: Buffer.concat([ct, cipher.getAuthTag()]).toString("base64"),
  };
}

function decryptSecret(enc, password) {
  const key = deriveKey(password, Buffer.from(enc.salt, "base64"));
  const nonce = Buffer.from(enc.nonce, "base64");
  const blob = Buffer.from(enc.data, "base64");
  const tag = blob.slice(-16);
  const ct = blob.slice(0, -16);
  const dec = crypto.createDecipheriv("aes-256-gcm", key, nonce);
  dec.setAuthTag(tag);
  return Buffer.concat([dec.update(ct), dec.final()]);
}

async function createWallet(name, network) {
  const p = walletPath(name);
  if (fs.existsSync(p)) throw new WalletError(`wallet '${name}' already exists`);
  const password = await promptPassword("Set a password for this wallet: ");
  if (!password || password.length < 8) throw new WalletError("password must be at least 8 characters");
  const confirm = await promptPassword("Confirm password: ");
  if (password !== confirm) throw new WalletError("passwords do not match");

  const kp = sol.generateKeypair();
  const address = sol.pubkeyToAddress(kp.publicKey);
  const doc = {
    v: 1,
    name,
    address,
    network: network || "mainnet",
    created_at: new Date().toISOString(),
    enc: encryptSecret(kp.secretKey, password),
  };
  fs.mkdirSync(WALLETS_DIR, { mode: 0o700, recursive: true });
  const tmp = p + `.tmp-${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(doc, null, 2), { mode: 0o600 });
  fs.renameSync(tmp, p);
  fs.chmodSync(p, 0o600);
  return { name, address, network: doc.network };
}

function listWallets() {
  let files = [];
  try {
    files = fs.readdirSync(WALLETS_DIR).filter((f) => f.endsWith(".json"));
  } catch {
    return [];
  }
  return files.map((f) => {
    try {
      const doc = JSON.parse(fs.readFileSync(path.join(WALLETS_DIR, f), "utf8"));
      return { name: doc.name || f.replace(/\.json$/, ""), address: doc.address, network: doc.network, created_at: doc.created_at };
    } catch {
      return { name: f.replace(/\.json$/, ""), address: "unreadable", network: "?", created_at: null };
    }
  });
}

async function loadSecretKey(name) {
  const p = walletPath(name);
  if (!fs.existsSync(p)) throw new WalletError(`wallet '${name}' not found — create it with \`musebook wallet create --name ${name}\``);
  const doc = JSON.parse(fs.readFileSync(p, "utf8"));
  const password = await promptPassword(`Password for wallet '${name}': `);
  let secret;
  try {
    secret = decryptSecret(doc.enc, password);
  } catch {
    throw new WalletError("wrong password (or corrupted wallet file)");
  }
  if (secret.length !== 64) throw new WalletError("corrupted wallet file");
  return { secretKey: secret, address: doc.address, network: doc.network };
}

module.exports = { WalletError, createWallet, listWallets, loadSecretKey, promptPassword, WALLETS_DIR };
