#!/usr/bin/env node
// Solana Tracker Datastream listener.
// Connects to wss://datastream.solanatracker.io/{key}/ using the stored
// custom.solana-tracker-datastream credential (surrogate in URL path,
// swapped for the real key by the egress proxy).
//
// The WS URL is passed via DATASTREAM_WS_URL env (built by ds.py).
// Usage: ds.py [--seconds N] [--limit N] [--rooms latest,graduating]
//              [--token MINT (joins price-by-token + volume rooms)]
//              [--raw]
//
// Wire protocol (from @solana-tracker/data-api SDK):
//   -> {"type":"join","room":"latest"}
//   -> {"type":"leave","room":"latest"}
//   <- {"type":"ping"}  -> respond {"type":"pong"}
//   <- {"type":"message", room, data}  (event payloads)

import WebSocket from "ws";
import { HttpsProxyAgent } from "https-proxy-agent";

const WS_URL = process.env.DATASTREAM_WS_URL;
if (!WS_URL) {
  console.error("[datastream] DATASTREAM_WS_URL not set — run via ds.py");
  process.exit(2);
}

const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY || null;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;

function arg(name, def = null) {
  const i = process.argv.indexOf(name);
  return i !== -1 && i + 1 < process.argv.length ? process.argv[i + 1] : def;
}
const has = (name) => process.argv.includes(name);

const seconds = parseFloat(arg("--seconds", "30"));
const limit = arg("--limit") ? parseInt(arg("--limit"), 10) : Infinity;
const rooms = (arg("--rooms", "latest") || "").split(",").map((s) => s.trim()).filter(Boolean);
const token = arg("--token");
const raw = has("--raw");

if (token) {
  rooms.push(`price-by-token:${token}`, `volume:token:${token}`);
}

let seen = 0;
let stopping = false;
const t0 = Date.now();

const ws = new WebSocket(WS_URL, {
  agent,
  headers: { "User-Agent": "solana-tracker-datastream-skill/1.0" },
  handshakeTimeout: 20000,
});

function done(reason) {
  if (stopping) return;
  stopping = true;
  console.error(`[datastream] done: ${reason} (${seen} events, ${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  try { for (const r of rooms) ws.send(JSON.stringify({ type: "leave", room: r })); } catch {}
  ws.close();
  setTimeout(() => process.exit(0), 300);
}

ws.on("open", () => {
  console.error(`[datastream] connected (${rooms.length} rooms)`);
  for (const r of rooms) ws.send(JSON.stringify({ type: "join", room: r }));
});

ws.on("message", (buf) => {
  if (stopping) return;
  let m;
  try { m = JSON.parse(buf.toString("utf8")); }
  catch { if (raw) process.stdout.write(buf.toString() + "\n"); return; }

  if (m.type === "ping") { try { ws.send(JSON.stringify({ type: "pong" })); } catch {} return; }
  if (raw) { process.stdout.write(JSON.stringify(m) + "\n"); seen++; }
  else if (m.type === "message") {
    // slim the event: keep room + core payload
    const d = m.data || m;
    const out = { type: "datastream", room: m.room || null };
    for (const k of ["mint", "tokenAddress", "name", "symbol", "price", "priceUsd",
                     "marketCap", "marketCapUsd", "volume", "volumeUsd", "txns",
                     "buys", "sells", "holders", "liquidity", "liquidityUsd",
                     "signature", "slot", "timestamp", "poolId", "curve"]) {
      if (d[k] !== undefined && d[k] !== null) out[k] = d[k];
    }
    if (d.token && typeof d.token === "object") {
      for (const k of ["mint", "name", "symbol"]) if (d.token[k]) out[k] = d.token[k];
    }
    process.stdout.write(JSON.stringify(out) + "\n");
    seen++;
  } else {
    process.stdout.write(JSON.stringify({ type: "datastream", kind: m.type, room: m.room || null }) + "\n");
    seen++;
  }
  if (seen >= limit) done("limit reached");
});

ws.on("error", (e) => console.error("[datastream] error:", e.message));
ws.on("close", (code, reason) => {
  console.error(`[datastream] closed (${code}) ${reason || ""}`);
  if (!stopping) process.exit(1);
});

setTimeout(() => done("time up"), seconds * 1000);
