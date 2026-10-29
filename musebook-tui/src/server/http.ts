import {
  createServer,
  type IncomingMessage,
  type Server,
  type ServerResponse,
} from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import type { AgentConfig } from '../config.js';
import { isFreeModel } from '../config.js';
import { fetchModels, per1M } from '../models.js';
import { SessionManager } from './sessions.js';
import { openSse, sendSse } from './protocol.js';
import { closeMcp } from '../mcp.js';

export interface ServerOptions {
  config: AgentConfig;
  token: string;
  host: string;
  port: number;
  corsOrigins: string[];
  version: string;
}

const MAX_BODY = 1_048_576; // 1 MB
const RATE_LIMIT = 120; // requests per minute per IP

function json(res: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
  });
  res.end(payload);
}

function clientIp(req: IncomingMessage): string {
  const fwd = req.headers['x-forwarded-for'];
  if (typeof fwd === 'string' && fwd) return fwd.split(',')[0].trim();
  return req.socket.remoteAddress ?? 'unknown';
}

/** Constant-time bearer comparison. */
function bearerOk(req: IncomingMessage, token: string): boolean {
  const h = req.headers.authorization;
  if (typeof h !== 'string' || !h.startsWith('Bearer ')) return false;
  const given = Buffer.from(h.slice(7));
  const want = Buffer.from(token);
  return given.length === want.length && timingSafeEqual(given, want);
}

function readBody(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks: Buffer[] = [];
    const timer = setTimeout(() => reject(new Error('body timeout')), 30_000);
    req.on('data', (c: Buffer) => {
      size += c.length;
      if (size > MAX_BODY) {
        clearTimeout(timer);
        reject(new Error('body too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => {
      clearTimeout(timer);
      const raw = Buffer.concat(chunks).toString('utf-8');
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error('invalid JSON'));
      }
    });
    req.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

export function startServer(opts: ServerOptions): Server {
  const manager = new SessionManager(opts.config);
  const hits = new Map<string, number[]>();

  const allowed = (req: IncomingMessage, res: ServerResponse): boolean => {
    // Rate limit (per IP, sliding 60s window).
    const ip = clientIp(req);
    const now = Date.now();
    const window = (hits.get(ip) ?? []).filter((t) => now - t < 60_000);
    window.push(now);
    hits.set(ip, window);
    if (window.length > RATE_LIMIT) {
      json(res, 429, { error: 'rate limited' });
      return false;
    }
    // Auth.
    const url = new URL(req.url ?? '/', 'http://localhost');
    const isSse = req.method === 'GET' && /^\/v1\/sessions\/[^/]+\/stream$/.test(url.pathname);
    if (isSse && url.searchParams.get('token') === opts.token) return true; // EventSource can't set headers
    if (!bearerOk(req, opts.token)) {
      json(res, 401, { error: 'unauthorized' });
      return false;
    }
    return true;
  };

  const cors = (req: IncomingMessage, res: ServerResponse): boolean => {
    if (opts.corsOrigins.length === 0) return true;
    const origin = req.headers.origin;
    if (origin && opts.corsOrigins.includes(origin)) {
      res.setHeader('Access-Control-Allow-Origin', origin);
      res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
    }
    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return false;
    }
    return true;
  };

  const server = createServer(async (req, res) => {
    try {
      if (!cors(req, res)) return;
      const url = new URL(req.url ?? '/', 'http://localhost');
      const path = url.pathname;

      if (req.method === 'GET' && path === '/healthz') {
        return json(res, 200, { ok: true, version: opts.version, time: new Date().toISOString() });
      }

      if (!allowed(req, res)) return;

      // POST /v1/sessions
      if (req.method === 'POST' && path === '/v1/sessions') {
        const body = (await readBody(req)) as { model?: string };
        const s = manager.create(typeof body.model === 'string' ? body.model : undefined);
        return json(res, 201, { id: s.id, created_at: s.createdAt, model: s.config.model });
      }

      // GET /v1/sessions
      if (req.method === 'GET' && path === '/v1/sessions') {
        return json(res, 200, { sessions: manager.list() });
      }

      const m = path.match(/^\/v1\/sessions\/([^/]+)(?:\/(stream|messages|decisions|model))?$/);
      if (!m) return json(res, 404, { error: 'not found' });
      const [, id, sub] = m;
      const s = manager.get(id);
      if (!s) return json(res, 404, { error: 'unknown session' });

      // GET /v1/sessions/:id
      if (req.method === 'GET' && !sub) {
        return json(res, 200, {
          id: s.id,
          created_at: s.createdAt,
          model: s.config.model,
          running: s.running,
          clients: s.clients.size,
          totals: s.totals,
          transcript_length: s.transcript.length,
        });
      }

      // DELETE /v1/sessions/:id
      if (req.method === 'DELETE' && !sub) {
        manager.delete(id);
        return json(res, 200, { deleted: true });
      }

      // GET /v1/sessions/:id/stream — SSE
      if (req.method === 'GET' && sub === 'stream') {
        openSse(res, id);
        manager.subscribe(s, res);
        return;
      }

      // POST /v1/sessions/:id/messages
      if (req.method === 'POST' && sub === 'messages') {
        const body = (await readBody(req)) as { message?: string };
        const message = typeof body.message === 'string' ? body.message.trim() : '';
        if (!message) return json(res, 400, { error: 'message is required' });
        if (message.length > 20_000) return json(res, 400, { error: 'message too long' });
        // Don't await the turn — results stream over SSE.
        void manager.send(id, message);
        return json(res, 202, { accepted: true, session_id: id });
      }

      // POST /v1/sessions/:id/decisions
      if (req.method === 'POST' && sub === 'decisions') {
        const body = (await readBody(req)) as { call_id?: string; approved?: boolean };
        if (typeof body.call_id !== 'string' || typeof body.approved !== 'boolean') {
          return json(res, 400, { error: 'call_id (string) and approved (boolean) are required' });
        }
        const resolved = manager.decide(id, body.call_id, body.approved);
        if (!resolved) return json(res, 404, { error: 'unknown or expired approval' });
        return json(res, 200, { resolved: true });
      }

      // POST /v1/sessions/:id/model — pricing-aware switch, mirrors /model
      if (req.method === 'POST' && sub === 'model') {
        const body = (await readBody(req)) as { model?: string; confirm?: boolean };
        const wanted = typeof body.model === 'string' ? body.model.trim() : '';
        if (!wanted) return json(res, 400, { error: 'model is required' });
        let models;
        try {
          models = await fetchModels(opts.config.apiKey);
        } catch (err) {
          return json(res, 502, { error: `model catalog unreachable: ${(err as Error).message}` });
        }
        const found = models.find((x) => x.id === wanted);
        if (!found) return json(res, 404, { error: `unknown model: ${wanted}` });
        if (!isFreeModel(found.id) && !body.confirm) {
          return json(res, 402, {
            needs_confirm: true,
            id: found.id,
            name: found.name,
            prompt_per_1m: per1M(found.pricing?.prompt),
            completion_per_1m: per1M(found.pricing?.completion),
            hint: 're-post with {"model": "...", "confirm": true} to switch to this paid model',
          });
        }
        s.config.model = found.id;
        return json(res, 200, { model: s.config.model });
      }

      return json(res, 404, { error: 'not found' });
    } catch (err) {
      if (!res.headersSent) json(res, 500, { error: (err as Error).message });
    }
  });

  server.on('clientError', (_err, socket) => socket.destroy());

  const shutdown = async () => {
    server.close();
    await closeMcp();
    process.exit(0);
  };
  process.on('SIGINT', () => void shutdown());
  process.on('SIGTERM', () => void shutdown());

  server.listen(opts.port, opts.host, () => {
    console.log(`🦞 musebook-tui server v${opts.version} on http://${opts.host}:${opts.port}`);
    console.log(`   health:  GET /healthz (no auth)`);
    console.log(`   api:     /v1/sessions… (Bearer ${opts.token.slice(0, 4)}…${opts.token.slice(-4)})`);
    console.log(`   OPENROUTER_API_KEY stays server-side — never sent to SSE/browser clients.`);
  });

  return server;
}

// Re-export for tests.
export { sendSse };
