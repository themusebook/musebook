#!/usr/bin/env node
// DFlow live quote stream — top-of-book bid/ask for a token pair.
// Usage: node dflow_stream.mjs --url <ws_url> --base <mint> --quote <mint>
//        [--seconds N] [--surrogate <x-api-key surrogate>] [--raw]
// Prints one compact JSON object per update on stdout.
// The surrogate is a proxy-resolved credential reference, never the raw key;
// it is passed via argv and never logged.
import WebSocket from "ws";
import { HttpsProxyAgent } from "https-proxy-agent";

function arg(name, def = null) {
  const i = process.argv.indexOf(name);
  return i !== -1 && i + 1 < process.argv.length ? process.argv[i + 1] : def;
}
const has = (name) => process.argv.includes(name);

const url = arg("--url");
const baseMint = arg("--base");
const quoteMint = arg("--quote");
const seconds = parseFloat(arg("--seconds", "15"));
const surrogate = arg("--surrogate", null);
const raw = has("--raw");
if (!url || !baseMint || !quoteMint) {
  console.error("usage: dflow_stream.mjs --url <ws> --base <mint> --quote <mint> [--seconds N] [--surrogate S] [--raw]");
  process.exit(2);
}

const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY || null;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
const headers = { Origin: "https://quote-api.dflow.net", "User-Agent": "dflow-skill/1.0" };
if (surrogate) headers["x-api-key"] = surrogate;

let seen = 0, stopping = false;
const t0 = Date.now();
const ws = new WebSocket(url, { agent, headers, handshakeTimeout: 15000 });

function done(reason) {
  if (stopping) return;
  stopping = true;
  console.error(`[dflow-stream] done: ${reason} (${seen} updates, ${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  try { ws.close(); } catch {}
  setTimeout(() => process.exit(0), 300);
}

ws.on("open", () => {
  console.error(`[dflow-stream] connected`);
  ws.send(JSON.stringify({ op: "subscribe", base_mint: baseMint, quote_mint: quoteMint }));
});
ws.on("message", (buf) => {
  if (stopping) return;
  const text = buf.toString("utf8");
  let frame;
  try { frame = JSON.parse(text); }
  catch { if (raw) process.stdout.write(text + "\n"); return; }
  for (const u of frame.updates ?? []) {
    seen++;
    if (raw) { process.stdout.write(JSON.stringify(u) + "\n"); continue; }
    if (u.e) { process.stdout.write(JSON.stringify({ slot: frame.u, err: u.e }) + "\n"); continue; }
    process.stdout.write(JSON.stringify({
      slot: frame.u, ts: frame.ts,
      bid: u.b, ask: u.a, bidSize: u.B, askSize: u.A,
    }) + "\n");
  }
  if ((Date.now() - t0) / 1000 >= seconds) done("time elapsed");
});
ws.on("error", (e) => done(`error: ${e.message}`));
ws.on("close", (code, reason) => done(`closed code=${code} ${reason.toString().slice(0, 80)}`));
setTimeout(() => done("timeout"), (seconds + 15) * 1000);
