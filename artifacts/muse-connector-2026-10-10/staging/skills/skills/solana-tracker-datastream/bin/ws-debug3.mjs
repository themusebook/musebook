// Direct connection (no proxy) to isolate proxy vs origin behavior
import WebSocket from "ws";
const url = process.env.DATASTREAM_WS_URL;
const ws = new WebSocket(url, { handshakeTimeout: 15000 });
ws.on('unexpected-response', (req, res) => {
  console.error('STATUS:', res.statusCode, 'CONN:', res.headers.connection, 'UPGRADE:', res.headers.upgrade);
  process.exit(0);
});
ws.on('open', () => { console.error('OPEN OK'); process.exit(0); });
ws.on('error', e => console.error('ERR:', e.message));
setTimeout(() => { console.error('TIMEOUT'); process.exit(1); }, 20000);
