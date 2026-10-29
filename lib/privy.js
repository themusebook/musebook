/**
 * lib/privy.js — Privy OAuth 2.0 Device Authorization Grant for the Musebook CLI.
 *
 * Approve once in the browser at https://musebook.trade/authorize, then sign
 * with the user's Privy embedded Solana wallets headlessly. No Privy app
 * secret is required or used anywhere — device flows are public-client by
 * design.
 *
 * SOLANA ONLY. Every wallet operation verifies chain_type === "solana" and
 * refuses anything else.
 *
 * Security model (mirrors the privy-device-auth skill):
 * - Never printed/logged: access tokens, refresh tokens, device codes,
 *   decrypted wallet authorization keys. Status shows presence/expiry only.
 * - Session storage: AES-256-GCM file at ~/.config/musebook-cli/privy-session.enc
 *   (dir 0700, file 0600, atomic writes), key derived machine-bound via
 *   HKDF-SHA256. A loud warning is printed because this is weaker than a keychain.
 * - The decrypted wallet authorization key is memory-only, cached in-process
 *   until its expires_at, never written to disk.
 * - signTransaction signs only. Nothing here broadcasts to Solana.
 */
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const APP_ID = process.env.PRIVY_APP_ID || "cm7tbyvvy01w2144yss67bjm0";
const BASE_URL = (process.env.PRIVY_API_BASE_URL || "https://auth.privy.io").replace(/\/+$/, "");
const VERIFY_PAGE = "https://musebook.trade/authorize";
const GRANT_TYPE_DEVICE = "urn:ietf:params:oauth:grant-type:device_code";
const GRANT_TYPE_REFRESH = "refresh_token";
const EXPIRY_SKEW = 60; // refresh this many seconds before access-token expiry

const CONFIG_DIR = path.join(os.homedir(), ".config", "musebook-cli");
const SESSION_FILE = path.join(CONFIG_DIR, "privy-session.enc");
const PENDING_FILE = path.join(CONFIG_DIR, "privy-login.enc");

class PrivyError extends Error {}

// ---------------------------------------------------------------------------
// http
// ---------------------------------------------------------------------------

async function privyHttp(method, apiPath, { body = null, headers = {} } = {}) {
  const url = BASE_URL + apiPath;
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: {
        "content-type": "application/json",
        accept: "application/json",
        "privy-app-id": APP_ID,
        ...headers,
      },
      body: body === null ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(20000),
    });
  } catch (e) {
    throw new PrivyError(`network error: ${e.message}`);
  }
  const text = await res.text().catch(() => "");
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { raw: text.slice(0, 200) };
  }
  return { status: res.status, payload };
}

function errStr(payload, status) {
  if (payload && typeof payload === "object") {
    return payload.error || payload.message || payload.code || `HTTP ${status}`;
  }
  return `HTTP ${status}`;
}

async function httpRetry(method, apiPath, opts = {}, attempts = 5) {
  let delay = 1000;
  let last;
  for (let i = 0; i < attempts; i++) {
    try {
      return await privyHttp(method, apiPath, opts);
    } catch (e) {
      last = e;
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, delay));
        delay *= 2;
      }
    }
  }
  throw last;
}

// ---------------------------------------------------------------------------
// RFC 8785 JSON Canonicalization (JCS) — sufficient for our ASCII payloads
// ---------------------------------------------------------------------------

function jcs(value) {
  if (value === null || value === undefined) return "null";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new PrivyError("non-finite number in JCS payload");
    return JSON.stringify(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) return "[" + value.map(jcs).join(",") + "]";
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + jcs(value[k])).join(",") + "}";
  }
  throw new PrivyError("unsupported type in JCS payload");
}

// ---------------------------------------------------------------------------
// HPKE base mode: DHKEM(P-256) / HKDF-SHA256 / ChaCha20-Poly1305 (RFC 9180)
// ---------------------------------------------------------------------------

const HPKE_SUITE_ID = Buffer.concat([
  Buffer.from("HPKE", "ascii"),
  Buffer.from([0x00, 0x10]), // KEM: DHKEM(P-256)
  Buffer.from([0x00, 0x01]), // KDF: HKDF-SHA256
  Buffer.from([0x00, 0x03]), // AEAD: ChaCha20-Poly1305
]);

// RFC 9180 §4.1: the KEM's own LabeledExtract uses suite_id = "KEM" || kem_id,
// NOT the full HPKE suite id (that one is only for the §5.1 key schedule).
const KEM_SUITE_ID = Buffer.concat([
  Buffer.from("KEM", "ascii"),
  Buffer.from([0x00, 0x10]), // KEM: DHKEM(P-256)
]);

function hkdfExtract(salt, ikm) {
  const s = salt && salt.length ? Buffer.from(salt) : Buffer.alloc(32, 0);
  return crypto.createHmac("sha256", s).update(Buffer.from(ikm)).digest();
}

function hkdfExpand(prk, info, length) {
  const infoBuf = Buffer.from(info);
  const n = Math.ceil(length / 32);
  let t = Buffer.alloc(0);
  let okm = Buffer.alloc(0);
  for (let i = 1; i <= n; i++) {
    t = crypto.createHmac("sha256", prk).update(Buffer.concat([t, infoBuf, Buffer.from([i])])).digest();
    okm = Buffer.concat([okm, t]);
  }
  return okm.slice(0, length);
}

function labeledExtract(salt, label, ikm, suiteId = HPKE_SUITE_ID) {
  const labeledIkm = Buffer.concat([
    Buffer.from("HPKE-v1", "ascii"),
    suiteId,
    Buffer.from(label, "ascii"),
    Buffer.from(ikm),
  ]);
  return hkdfExtract(salt, labeledIkm);
}

function labeledExpand(prk, label, info, length, suiteId = HPKE_SUITE_ID) {
  const lenPrefix = Buffer.alloc(2);
  lenPrefix.writeUInt16BE(length, 0);
  const labeledInfo = Buffer.concat([
    lenPrefix,
    Buffer.from("HPKE-v1", "ascii"),
    suiteId,
    Buffer.from(label, "ascii"),
    Buffer.from(info),
  ]);
  return hkdfExpand(prk, labeledInfo, length);
}

/** Decrypt enc||ciphertext with our P-256 private key (base mode, empty info/aad). */
function hpkeDecrypt(enc, ciphertext, skR) {
  if (enc.length !== 65 || enc[0] !== 0x04) throw new PrivyError("bad HPKE encapsulated key");
  const ecdh = crypto.createECDH("prime256v1");
  ecdh.setPrivateKey(Buffer.from(skR));
  const pkRm = ecdh.getPublicKey(); // our uncompressed public key, 65 bytes
  const dh = ecdh.computeSecret(enc); // 32-byte x-coordinate
  const kemContext = Buffer.concat([enc, pkRm]);
  // RFC 9180 §4.1 DHKEM: Extract-and-Expand, NOT a single extract.
  // Both steps use the KEM suite id ("KEM" || kem_id).
  const eaePrk = labeledExtract(Buffer.alloc(0), "eae_prk", dh, KEM_SUITE_ID);
  const sharedSecret = labeledExpand(eaePrk, "shared_secret", kemContext, 32, KEM_SUITE_ID);

  // §5.1 key schedule uses the full HPKE suite id.
  // Note: secret = LabeledExtract(shared_secret, "secret", psk) where psk is
  // EMPTY in base mode — psk_id_hash only goes into key_schedule_context.
  const pskIdHash = labeledExtract(Buffer.alloc(0), "psk_id_hash", Buffer.alloc(0));
  const infoHash = labeledExtract(Buffer.alloc(0), "info_hash", Buffer.alloc(0));
  const keyScheduleContext = Buffer.concat([Buffer.from([0x00]), pskIdHash, infoHash]);
  const secret = labeledExtract(sharedSecret, "secret", Buffer.alloc(0));
  const key = labeledExpand(secret, "key", keyScheduleContext, 32);
  // NOTE: the label is "base_nonce" (underscore). This matches both the
  // `cryptography` Suite and @hpke/core, which interoperate with Privy.
  const baseNonce = labeledExpand(secret, "base_nonce", keyScheduleContext, 12);

  const ct = Buffer.from(ciphertext);
  if (ct.length < 16) throw new PrivyError("HPKE ciphertext too short");
  const tag = ct.slice(-16);
  const data = ct.slice(0, -16);
  const dec = crypto.createDecipheriv("chacha20-poly1305", key, baseNonce);
  dec.setAuthTag(tag);
  return Buffer.concat([dec.update(data), dec.final()]);
}

/** SPKI DER of an uncompressed P-256 public key, for recipient_public_key. */
function spkiDerP256(uncompressed65) {
  const prefix = Buffer.from("3059301306072a8648ce3d020106082a8648ce3d030107034200", "hex");
  return Buffer.concat([prefix, Buffer.from(uncompressed65)]);
}

// ---------------------------------------------------------------------------
// session storage: AES-256-GCM file, machine-bound key
// ---------------------------------------------------------------------------

function machineId() {
  try {
    const id = fs.readFileSync("/etc/machine-id", "utf8").trim();
    if (id) return id;
  } catch {}
  try {
    const id = fs.readFileSync("/etc/hostid", "utf8").trim();
    if (id) return id;
  } catch {}
  return `${os.hostname()}:${os.homedir()}`; // fallback (weaker)
}

function fileKey() {
  return hkdfExpand(
    hkdfExtract(Buffer.from("musebook-cli-privy-session-v1", "utf8"), Buffer.from(machineId(), "utf8")),
    Buffer.from("session-encryption", "utf8"),
    32
  );
}

function warnFileFallback() {
  console.error(
    "  NOTE: session is stored in an encrypted file (no OS keychain integration " +
      "in this build). It is bound to this machine, but a keychain would be stronger."
  );
}

function encryptedSave(file, sess) {
  const key = fileKey();
  const nonce = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, nonce);
  const ct = Buffer.concat([cipher.update(JSON.stringify(sess), "utf8"), cipher.final()]);
  const payload = {
    v: 1,
    nonce: nonce.toString("base64"),
    data: Buffer.concat([ct, cipher.getAuthTag()]).toString("base64"),
  };
  fs.mkdirSync(CONFIG_DIR, { mode: 0o700, recursive: true });
  const tmp = file + `.tmp-${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(payload), { mode: 0o600 });
  fs.renameSync(tmp, file);
  fs.chmodSync(CONFIG_DIR, 0o700);
  fs.chmodSync(file, 0o600);
}

function encryptedLoad(file) {
  let raw;
  try {
    raw = fs.readFileSync(file, "utf8");
  } catch {
    return null;
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return null;
  }
  try {
    const key = fileKey();
    const nonce = Buffer.from(payload.nonce, "base64");
    const blob = Buffer.from(payload.data, "base64");
    const tag = blob.slice(-16);
    const ct = blob.slice(0, -16);
    const dec = crypto.createDecipheriv("aes-256-gcm", key, nonce);
    dec.setAuthTag(tag);
    const pt = Buffer.concat([dec.update(ct), dec.final()]);
    return JSON.parse(pt.toString("utf8"));
  } catch {
    return null;
  }
}

function sessionSave(sess) {
  encryptedSave(SESSION_FILE, sess);
  warnFileFallback();
}

function sessionLoad() {
  return encryptedLoad(SESSION_FILE);
}

function pendingDelete() {
  try { fs.unlinkSync(PENDING_FILE); } catch {}
}

function sessionDelete() {
  pendingDelete();
  try {
    fs.unlinkSync(SESSION_FILE);
  } catch {}
}

// ---------------------------------------------------------------------------
// tokens
// ---------------------------------------------------------------------------

function isExpired(expiresAtIso) {
  if (!expiresAtIso) return true;
  const t = Date.parse(expiresAtIso);
  if (Number.isNaN(t)) return true;
  return Date.now() >= t;
}

async function refreshSession(sess) {
  if (!sess.refresh_token) throw new PrivyError("no refresh token stored — run `musebook login` again");
  const { status, payload } = await httpRetry("POST", "/api/oauth/v2/token", {
    body: { grant_type: GRANT_TYPE_REFRESH, refresh_token: sess.refresh_token },
  });
  if (status !== 200) {
    throw new PrivyError(`token refresh failed: ${errStr(payload, status)} — run \`musebook login\` again`);
  }
  // The old refresh token is invalidated immediately; persist the rotation atomically.
  const updated = {
    ...sess,
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    access_token_expires_at: new Date(Date.now() + Number(payload.expires_in || 900) * 1000).toISOString(),
  };
  if (!updated.access_token || !updated.refresh_token) throw new PrivyError("bad refresh response from Privy");
  sessionSave(updated);
  return updated;
}

async function ensureSession() {
  const sess = sessionLoad();
  if (!sess) throw new PrivyError("not logged in — run `musebook login` first");
  const exp = Date.parse(sess.access_token_expires_at || "");
  if (Number.isNaN(exp) || Date.now() > exp - EXPIRY_SKEW * 1000) {
    return refreshSession(sess);
  }
  return sess;
}

// ---------------------------------------------------------------------------
// device login
// ---------------------------------------------------------------------------

function pollAction(status, payload) {
  if (status === 200) return ["done", ""];
  const code = payload && payload.error;
  if (status === 400 && code === "authorization_pending") return ["wait", ""];
  if (status === 400 && code === "slow_down") return ["slow_down", ""];
  if (status === 400 && code === "expired_token") return ["expired", ""];
  if (status === 400 && code === "access_denied") return ["denied", ""];
  return ["fatal", errStr(payload, status)];
}

function pendingLoad() {
  const pending = encryptedLoad(PENDING_FILE);
  if (!pending || pending.app_id !== APP_ID || pending.base_url !== BASE_URL) return null;
  if (!pending.device_code || !pending.user_code || !Number.isFinite(pending.expires_at)) return null;
  return pending;
}

function pendingSummary(pending) {
  return {
    status: "pending",
    logged_in: false,
    user_code: pending.user_code,
    verification_uri: pending.verification_uri,
    verification_uri_complete: pending.verification_uri_complete,
    expires_at: new Date(pending.expires_at).toISOString(),
    retry_after: Math.max(0, Math.ceil((pending.next_poll_at - Date.now()) / 1000)),
  };
}

function pendingLoginStatus() {
  const pending = pendingLoad();
  return pending && pending.expires_at > Date.now() ? pendingSummary(pending) : null;
}

function loginSummary(sess) {
  return {
    status: "approved",
    logged_in: true,
    access_token_expires_at: sess.access_token_expires_at,
    wallet_discovery: sess.wallet_discovery || "unknown",
    ...(sess.wallet_discovery_error ? { warning: sess.wallet_discovery_error } : {}),
    solana_wallets: (sess.wallets || []).filter((w) => w.chain_type === "solana")
      .map((w) => ({ id: w.id, address: w.address })),
  };
}

async function startDeviceLogin() {
  const existing = pendingLoad();
  if (existing && existing.expires_at > Date.now()) return existing;
  const { status, payload } = await httpRetry("POST", "/api/oauth/v2/device_authorization", { body: {} });
  if (status !== 200) {
    if (status === 403 && payload && payload.error === "device_auth_not_enabled") {
      throw new PrivyError(
        "device authorization is not enabled for this Privy app " +
          "(dashboard: Authentication -> Advanced -> CLI and agent access)."
      );
    }
    throw new PrivyError(`device authorization failed: ${errStr(payload, status)}`);
  }
  const deviceCode = payload.device_code; // encrypted locally, never printed
  const userCode = payload.user_code;
  const verificationUri = payload.verification_uri || VERIFY_PAGE;
  const expiresIn = Number(payload.expires_in || 600);
  const interval = Math.max(Number(payload.interval || 5), 5);
  if (!deviceCode || !userCode) throw new PrivyError("unexpected device_authorization response from Privy");
  if (!Number.isFinite(expiresIn) || expiresIn <= 0 || !Number.isFinite(interval)) {
    throw new PrivyError("invalid device authorization lifetime from Privy");
  }
  const completeUrl = new URL(payload.verification_uri_complete || verificationUri);
  if (!payload.verification_uri_complete) completeUrl.searchParams.set("user_code", userCode);
  const pending = {
    app_id: APP_ID,
    base_url: BASE_URL,
    device_code: deviceCode,
    user_code: userCode,
    verification_uri: verificationUri,
    verification_uri_complete: completeUrl.toString(),
    expires_at: Date.now() + expiresIn * 1000,
    interval: interval * 1000,
    next_poll_at: Date.now() + interval * 1000,
  };
  encryptedSave(PENDING_FILE, pending);
  return pending;
}

async function deviceLogin({ mode = "wait", resumeOnly = false, json = false } = {}) {
  if (!["start", "check", "wait"].includes(mode)) throw new PrivyError("unknown login mode");
  let pending = pendingLoad();
  if (!pending && (resumeOnly || mode === "check")) {
    if (sessionLoad()) return loginSummary(await ensureSession());
    throw new PrivyError("no pending login - run `musebook login --start --json` first");
  }
  if (mode !== "check" && !resumeOnly) pending = await startDeviceLogin();
  if (!pending || Date.now() >= pending.expires_at) {
    pendingDelete();
    throw new PrivyError("device code expired. Run `musebook login` again.");
  }
  const progress = (...args) => (json ? console.error : console.log)(...args);
  if (mode !== "check" && !(json && mode === "start")) {
    progress("\n  To authorize this agent, visit:");
    progress(`    ${pending.verification_uri_complete}`);
    progress(`  Code: ${pending.user_code}`);
    progress(mode === "start"
      ? "  After the human approves, run `musebook login --check --json`."
      : "  Waiting for approval. Keep this terminal open; rerun `musebook login` to resume if interrupted.");
  }
  if (mode === "start") return pendingSummary(pending);
  let nextProgressAt = Date.now() + 30000;
  let tokens = null;
  for (;;) {
    if (Date.now() >= pending.expires_at) {
      pendingDelete();
      throw new PrivyError("device code expired. Run `musebook login` again.");
    }
    if (mode === "check" && Date.now() < pending.next_poll_at) return pendingSummary(pending);
    await new Promise((r) => setTimeout(r, Math.max(0, Math.min(pending.next_poll_at, pending.expires_at) - Date.now())));
    if (Date.now() >= pending.expires_at) continue;
    pending.next_poll_at = Date.now() + pending.interval;
    encryptedSave(PENDING_FILE, pending);
    let res;
    try {
      res = await privyHttp("POST", "/api/oauth/v2/token", {
        body: { grant_type: GRANT_TYPE_DEVICE, device_code: pending.device_code },
      });
    } catch (e) {
      console.error(`  (poll request failed, retrying: ${e.message})`);
      if (mode === "check") return { ...pendingSummary(pending), warning: "network_error" };
      continue;
    }
    const [action, detail] = pollAction(res.status, res.payload);
    if (action === "done") {
      tokens = res.payload;
      break;
    }
    if (action === "wait" || action === "slow_down" || res.status === 429 || res.status >= 500) {
      if (action === "slow_down" || res.status === 429) pending.interval += 5000;
      pending.next_poll_at = Date.now() + pending.interval;
      encryptedSave(PENDING_FILE, pending);
      if (mode === "check") return pendingSummary(pending);
      if (Date.now() >= nextProgressAt) {
        progress(`  Still waiting for approval of ${pending.user_code} (${Math.ceil((pending.expires_at - Date.now()) / 1000)}s remaining)...`);
        nextProgressAt = Date.now() + 30000;
      }
      continue;
    }
    if (action === "expired" || action === "denied") pendingDelete();
    if (action === "expired") throw new PrivyError("device code expired. Run `musebook login` again.");
    if (action === "denied") throw new PrivyError("authorization request was denied in the browser.");
    throw new PrivyError(`token polling failed: ${detail}`);
  }

  const sess = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    access_token_expires_at: new Date(Date.now() + Number(tokens.expires_in || 900) * 1000).toISOString(),
    wallets: [],
    wallet_discovery: "pending",
  };
  if (!sess.access_token || !sess.refresh_token) throw new PrivyError("unexpected token response from Privy");

  // Token exchange consumes the request. Persist approval before wallet discovery.
  sessionSave(sess);
  pendingDelete();
  progress("Approval received. Login saved; checking Solana wallets...");
  let warning;
  try {
    const authz = await walletAuthenticate(sess.access_token);
    sess.wallets = authz.wallets;
    sess.wallet_discovery = "complete";
    authzCache = authz;
    sessionSave(sess);
  } catch (e) {
    warning = `Login saved, but wallet discovery failed: ${e.message}. Retry with musebook wallets.`;
    sess.wallet_discovery = "failed";
    sess.wallet_discovery_error = warning;
    sessionSave(sess);
    console.error(warning);
  }
  const result = loginSummary(sess);
  if (warning) result.warning = warning;
  if (!json) {
    console.log("Logged in. Run `musebook status` to check your session.");
    for (const w of result.solana_wallets) console.log(`  ${w.address} (${w.id})`);
    if (!warning && !result.solana_wallets.length) console.log("  No Solana wallets on this grant yet.");
  }
  return result;
}

// ---------------------------------------------------------------------------
// wallet authentication (HPKE) — the decrypted key is MEMORY ONLY
// ---------------------------------------------------------------------------

let authzCache = null; // { key, expiresAt, wallets }

async function walletAuthenticate(accessToken) {
  const ecdh = crypto.createECDH("prime256v1");
  ecdh.generateKeys();
  const recipientB64 = spkiDerP256(ecdh.getPublicKey()).toString("base64");

  const { status, payload } = await httpRetry(
    "POST",
    "/api/oauth/v2/wallets/authenticate",
    {
      headers: { Authorization: `Bearer ${accessToken}`, "privy-grant-type": "device_code" },
      body: { encryption_type: "HPKE", recipient_public_key: recipientB64 },
    }
  );
  if (status !== 200) throw new PrivyError(`wallet authentication failed: ${errStr(payload, status)}`);
  let enc, ct, expiresAt, wallets;
  try {
    enc = Buffer.from(payload.encrypted_authorization_key.encapsulated_key, "base64");
    ct = Buffer.from(payload.encrypted_authorization_key.ciphertext, "base64");
    expiresAt = payload.expires_at;
    wallets = payload.wallets || [];
  } catch (e) {
    throw new PrivyError(`unexpected wallets/authenticate response: ${e.message}`);
  }
  let plain;
  try {
    plain = hpkeDecrypt(enc, ct, ecdh.getPrivateKey());
  } catch (e) {
    throw new PrivyError(`HPKE decryption of the authorization key failed: ${e.message}`);
  }
  const keyStr = plain.toString("utf8").trim();
  if (!keyStr) throw new PrivyError("empty authorization key returned by Privy");
  return { key: keyStr, expiresAt, wallets };
}

async function ensureAuthz(sess) {
  if (!authzCache || isExpired(authzCache.expiresAt)) {
    let a;
    try {
      a = await walletAuthenticate(sess.access_token);
    } catch (e) {
      sessionSave({ ...sess, wallet_discovery: "failed", wallet_discovery_error: e.message });
      throw e;
    }
    authzCache = a;
    sessionSave({ ...sess, wallets: a.wallets, wallet_discovery: "complete", wallet_discovery_error: undefined });
  }
  return authzCache;
}

function findSolanaWallet(wallets, walletId) {
  const w = wallets.find((x) => x.id === walletId);
  if (!w) throw new PrivyError(`wallet '${walletId}' is not in this session's wallet list; refusing to sign.`);
  if (w.chain_type !== "solana") {
    throw new PrivyError(`wallet '${walletId}' is chain_type '${w.chain_type}', not solana; refusing.`);
  }
  return w;
}

// ---------------------------------------------------------------------------
// request authorization signatures (ECDSA P-256 over JCS)
// ---------------------------------------------------------------------------

function loadP256Key(keyStr) {
  let key;
  if (keyStr.startsWith("-----BEGIN")) {
    key = crypto.createPrivateKey({ key: keyStr, format: "pem" });
  } else {
    key = crypto.createPrivateKey({
      key: Buffer.from(keyStr, "base64"),
      format: "der",
      type: "pkcs8",
    });
  }
  if (key.asymmetricKeyType !== "ec" || key.asymmetricKeyDetails.namedCurve !== "prime256v1") {
    throw new PrivyError("authorization key is not a P-256 private key");
  }
  return key;
}

/** Matches Privy's official agent CLI / go-sdk exactly. */
function authorizationSignature(authzKey, url, body) {
  let bodyForSig = body;
  if (!body || jcs(body) === "{}") bodyForSig = "";
  const payload = {
    version: 1,
    method: "POST",
    url,
    body: bodyForSig,
    headers: { "privy-app-id": APP_ID },
  };
  // Sign the canonical JSON directly with SHA-256. (Do NOT prehash and pass
  // algorithm=null: Node's crypto.sign(null, ...) hashes the input again,
  // producing signatures Privy rejects. Signing the message with 'sha256' is
  // byte-identical to the skill's Prehashed(digest) construction.)
  const key = loadP256Key(authzKey);
  const sigDer = crypto.sign("sha256", Buffer.from(jcs(payload), "utf8"), { key, dsaEncoding: "der" });
  return sigDer.toString("base64");
}

async function walletRpc(sess, walletId, method, params) {
  const authz = await ensureAuthz(sess);
  findSolanaWallet(authz.wallets, walletId); // membership + chain check before any network call
  const apiPath = `/api/oauth/v2/wallets/${walletId}/rpc`;
  const url = BASE_URL + apiPath;
  const body = { method, params };

  const call = async (accessToken) => {
    const sig = authorizationSignature(authz.key, url, body);
    return privyHttp("POST", apiPath, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "privy-grant-type": "device_code",
        "privy-authorization-signature": sig,
      },
      body,
    });
  };

  let res = await call(sess.access_token);
  if (res.status === 401) {
    // Access token expired: refresh once, retry once.
    const refreshed = await refreshSession(sess);
    const authz2 = await ensureAuthz(refreshed);
    findSolanaWallet(authz2.wallets, walletId);
    res = await call(refreshed.access_token);
    Object.assign(sess, refreshed);
  }
  if (res.status !== 200) throw new PrivyError(`wallet RPC failed: ${errStr(res.payload, res.status)}`);
  const data = res.payload && res.payload.data !== undefined ? res.payload.data : res.payload;
  if (!data || typeof data !== "object") throw new PrivyError("unexpected wallet RPC response shape");
  return data;
}

/** Sign an arbitrary message with a Privy Solana wallet. Returns base58 signature. */
async function signMessage(walletId, message) {
  const sess = await ensureSession();
  const msgB64 = Buffer.from(String(message), "utf8").toString("base64");
  const data = await walletRpc(sess, walletId, "signMessage", { message: msgB64, encoding: "base64" });
  const sig = data.signature || data.signedMessage || data;
  if (typeof sig !== "string") throw new PrivyError("unexpected signMessage response");
  return sig;
}

/**
 * Ask Privy to sign a base64 Solana transaction. Returns { signatures: [...] }.
 * SIGN ONLY — this function never broadcasts.
 */
async function signTransaction(walletId, txB64) {
  const sess = await ensureSession();
  const data = await walletRpc(sess, walletId, "signTransaction", {
    transaction: String(txB64).trim(),
    encoding: "base64",
  });
  return data;
}

async function listWallets() {
  const sess = await ensureSession();
  const authz = await ensureAuthz(sess);
  return authz.wallets.filter((w) => w.chain_type === "solana");
}

module.exports = {
  PrivyError,
  APP_ID,
  VERIFY_PAGE,
  deviceLogin,
  sessionLoad,
  sessionDelete,
  pendingLoginStatus,
  ensureSession,
  listWallets,
  signMessage,
  signTransaction,
  findSolanaWallet,
  // exported for tests
  _jcs: jcs,
  _hpkeDecrypt: hpkeDecrypt,
  _authorizationSignature: authorizationSignature,
  _pollAction: pollAction,
};
