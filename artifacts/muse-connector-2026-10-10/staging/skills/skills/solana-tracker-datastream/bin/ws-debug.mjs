import WebSocket from "ws";
import { HttpsProxyAgent } from "https-proxy-agent";
const url = process.env.DATASTREAM_WS_URL;
const proxyUrl = process.env.https_proxy || process.env.HTTPS_PROXY || null;
const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
const ws = new WebSocket(url, { agent, handshakeTimeout: 15000 });
ws.on('unexpected-response', (req, res) => {
  console.error('STATUS:', res.statusCode);
  console.error('HEADERS:', JSON.stringify(res.headers));
  let body = '';
  res.on('data', c => body += c);
  res.on('end', () => { console.error('BODY:', body.slice(0, 300)); process.exit(0); });
});
ws.on('error', e => console.error('ERR:', e.message));
ws.on('open', () => { console.error('OPEN!'); process.exit(0); });
setTimeout(() => { console.error('TIMEOUT'); process.exit(1); }, 20000);
