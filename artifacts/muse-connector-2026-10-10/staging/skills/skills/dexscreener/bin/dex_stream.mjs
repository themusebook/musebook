#!/usr/bin/env node
// dex_stream.mjs — realtime DEX Screener WebSocket feed.
// Connects to wss://api.dexscreener.com/<channel> (public, no auth).
// First message is a snapshot handshake {limit, data:[...]}, then streaming
// update arrays [...] as new boosts/profiles/takeovers/ads arrive.
//
// Usage:
//   node dex_stream.mjs [--channel NAME] [--seconds N] [--limit N]
//                       [--chain solana] [--raw]
//
// Channels: boosts-latest | boosts-top | profiles-latest | profiles-updates
//           | takeovers | ads
//
// Output: one compact JSON object per line on stdout.
// Errors/status go to stderr. Fails closed: nonzero exit if the socket
// errors or closes before any message is received.

import WebSocket from "ws";
import { HttpsProxyAgent } from "https-proxy-agent";

const CHANNELS = {
  "boosts-latest": "token-boosts/latest/v1",
  "boosts-top": "token-boosts/top/v1",
  "profiles-latest": "token-profiles/latest/v1",
  "profiles-updates": "token-profiles/recent-updates/v1",
  "takeovers": "community-takeovers/latest/v1",
  "ads": "ads/latest/v1",
};

function arg(name, def = null) {
  const i = process.argv.indexOf(name);
  return i !== -1 && i + 1 < process.argv.length ? process.argv[i + 1] : def;
}
const has = (name) => process.argv.includes(name);

const channelName = arg("--channel", "boosts-latest");
const path = CHANNELS[channelName];
if (!path) {
  console.error(`unknown channel: ${channelName} (choose: ${Object.keys(CHANNELS).join("|")})`);
  process.exit(2);
}
const seconds = parseFloat(arg("--seconds", "30"));
const maxItems = arg("--limit") ? parseInt(arg("--limit"), 10) : Infinity;
const chainFilter = arg("--chain", null);
const raw = has("--raw");

const WS_URL = `wss://api.dexscreener.com/${path}`;

// Route through the runtime egress proxy when present (ws does not read
// proxy env vars on its own). Reads the env var, never logs its value.
const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY || null;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;

let seen = 0;
let gotAny = false;
let stopping = false;
const t0 = Date.now();

function slim(item, event) {
  if (raw) return { event, channel: channelName, ...item };
  const out = {
    event, channel: channelName,
    chainId: item.chainId || null,
    tokenAddress: item.tokenAddress || null,
    url: item.url || null,
    description: (item.description || "").slice(0, 160) || null,
    icon: item.icon || null,
  };
  if (item.amount != null) out.boost = `${item.amount}/${item.totalAmount}`;
  if (item.claimDate) out.claimDate = item.claimDate;
  if (item.type) out.adType = item.type;
  if (Array.isArray(item.links)) {
    out.links = item.links.slice(0, 6).map((l) => `${l.type || "link"}:${l.url}`).filter(Boolean);
  }
  return out;
}

function emit(items, event) {
  for (const item of items) {
    if (chainFilter && item.chainId !== chainFilter) continue;
    process.stdout.write(JSON.stringify(slim(item, event)) + "\n");
    seen++;
    if (seen >= maxItems) { done("limit reached"); return; }
  }
}

function done(reason) {
  if (stopping) return;
  stopping = true;
  console.error(`[dex-stream] done: ${reason} (${seen} items, ${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  ws.close();
  setTimeout(() => process.exit(gotAny ? 0 : 3), 300);
}

const ws = new WebSocket(WS_URL, {
  agent,
  headers: { Origin: "https://api.dexscreener.com", "User-Agent": "dexscreener-skill/1.0" },
  handshakeTimeout: 15000,
});

ws.on("open", () => console.error(`[dex-stream] connected: ${channelName}`));

ws.on("message", (buf) => {
  if (stopping) return;
  gotAny = true;
  let d;
  try { d = JSON.parse(buf.toString("utf8")); }
  catch { if (raw) process.stdout.write(buf.toString() + "\n"); return; }
  if (d && typeof d === "object" && !Array.isArray(d) && Array.isArray(d.data)) {
    emit(d.data, "snapshot");           // handshake
  } else if (Array.isArray(d)) {
    emit(d, "update");                  // streaming update
  } else if (raw) {
    process.stdout.write(JSON.stringify({ event: "unknown", channel: channelName, ...d }) + "\n");
  }
});

ws.on("error", (e) => { console.error("[dex-stream] error:", e.message); if (!gotAny) process.exit(3); });
ws.on("close", () => { console.error("[dex-stream] closed"); process.exit(gotAny ? 0 : 3); });

setTimeout(() => done("time up"), seconds * 1000);
