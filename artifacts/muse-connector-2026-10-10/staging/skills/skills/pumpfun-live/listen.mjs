#!/usr/bin/env node
// pumpfun-live listener — streams real-time pump.fun token launches from
// the Clawd relay at wss://clawd-ws.fly.dev/ws (public, no auth).
//
// Usage:
//   node listen.mjs [--seconds N] [--limit N] [--min-mcap SOL]
//                   [--has-twitter] [--match REGEX] [--types token-launch,status]
//                   [--raw]
//
// Output: one compact JSON object per line on stdout (unless --raw).

import WebSocket from "ws";
import { HttpsProxyAgent } from "https-proxy-agent";

const WS_URL = "wss://clawd-ws.fly.dev/ws";

// Route through the runtime egress proxy when present (ws does not read
// proxy env vars on its own). Reads the env var, never logs its value.
const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY || null;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;

function arg(name, def = null) {
  const i = process.argv.indexOf(name);
  return i !== -1 && i + 1 < process.argv.length ? process.argv[i + 1] : def;
}
const has = (name) => process.argv.includes(name);

const seconds = parseFloat(arg("--seconds", "20"));
const limit = arg("--limit") ? parseInt(arg("--limit"), 10) : Infinity;
const minMcap = arg("--min-mcap") ? parseFloat(arg("--min-mcap")) : 0;
const needTwitter = has("--has-twitter");
const matchRe = arg("--match") ? new RegExp(arg("--match"), "i") : null;
const types = new Set((arg("--types", "token-launch") || "").split(",").map((s) => s.trim()).filter(Boolean));
const raw = has("--raw");

let seen = 0;
let stopping = false;
const t0 = Date.now();

const ws = new WebSocket(WS_URL, {
  agent,
  headers: { Origin: "https://clawd-ws.fly.dev", "User-Agent": "pumpfun-live-skill/1.0" },
  handshakeTimeout: 15000,
});

function done(reason) {
  if (stopping) return;
  stopping = true;
  console.error(`[pumpfun-live] done: ${reason} (${seen} events, ${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  ws.close();
  setTimeout(() => process.exit(0), 300);
}

ws.on("open", () => console.error(`[pumpfun-live] connected to ${WS_URL}`));

ws.on("message", (buf) => {
  if (stopping) return;
  let d;
  try { d = JSON.parse(buf.toString("utf8")); }
  catch { if (raw) process.stdout.write(buf.toString() + "\n"); return; }

  const type = d.type || "unknown";
  if (types.size && !types.has(type)) return;
  if (type === "token-launch") {
    if ((d.marketCapSol || 0) < minMcap) return;
    if (needTwitter && !d.twitter) return;
    if (matchRe) {
      const hay = `${d.name || ""} ${d.symbol || ""} ${d.description || ""}`;
      if (!matchRe.test(hay)) return;
    }
    const out = {
      type, time: d.time, name: d.name, symbol: d.symbol, mint: d.mint,
      creator: d.creator, marketCapSol: d.marketCapSol,
      twitter: d.twitter || null, telegram: d.telegram || null,
      website: d.website || null, imageUri: d.imageUri || null,
      description: (d.description || "").slice(0, 200) || null,
      signature: d.signature,
    };
    process.stdout.write(JSON.stringify(out) + "\n");
  } else {
    // status / other frame types pass through slimmed
    process.stdout.write(JSON.stringify({ type, ...d }) + "\n");
  }
  seen++;
  if (seen >= limit) done("limit reached");
});

ws.on("error", (e) => console.error("[pumpfun-live] error:", e.message));
ws.on("close", () => { console.error("[pumpfun-live] closed"); process.exit(0); });

setTimeout(() => done("time up"), seconds * 1000);
