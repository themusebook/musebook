import WebSocket from "ws";
import { HttpsProxyAgent } from "https-proxy-agent";
const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY || null;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
const ws = new WebSocket("wss://clawd-ws.fly.dev/ws", {
  agent,
  headers: { Origin: "https://clawd-ws.fly.dev" },
  handshakeTimeout: 15000,
});
ws.on('unexpected-response', (req, res) => {
  console.error('STATUS:', res.statusCode, 'CONN:', res.headers.connection, 'UPGRADE:', res.headers.upgrade);
  process.exit(0);
});
ws.on('open', () => { console.error('OPEN OK'); process.exit(0); });
ws.on('error', e => console.error('ERR:', e.message));
setTimeout(() => { console.error('TIMEOUT'); process.exit(1); }, 15000);
