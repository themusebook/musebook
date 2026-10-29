#!/usr/bin/env node
/**
 * musebook-tui-server — protected HTTP/SSE surface for website integration.
 *
 * The OpenRouter key stays server-side. Browser/website clients talk to this
 * server with a bearer token (TUI_SERVER_TOKEN) and receive the agent's
 * output over Server-Sent Events. They never see OPENROUTER_API_KEY.
 *
 *   TUI_SERVER_TOKEN=…  required — generate with: openssl rand -hex 32
 *   OPENROUTER_API_KEY=… required — inference key, server-side only
 *   TUI_HOST=127.0.0.1   bind address (keep loopback unless you know why not)
 *   TUI_PORT=8787
 *   TUI_CORS_ORIGINS=    comma-separated; empty = no CORS (server-to-server)
 *
 * Flow per session:
 *   POST /v1/sessions                 -> { id }
 *   GET  /v1/sessions/:id/stream      -> SSE (Authorization header or ?token=)
 *   POST /v1/sessions/:id/messages    -> { message } (202, streams over SSE)
 *   POST /v1/sessions/:id/decisions   -> { call_id, approved } (HITL round-trip)
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { randomBytes } from 'node:crypto';
import { loadConfig, loadDotEnv } from './config.js';
import { SYSTEM_PROMPT } from './system-prompt.js';
import { startServer } from './server/http.js';

function version(): string {
  try {
    const pkg = JSON.parse(readFileSync(resolve('package.json'), 'utf-8'));
    return String(pkg.version ?? '0.0.0');
  } catch {
    return '0.0.0';
  }
}

function main(): void {
  loadDotEnv();

  let token = process.env.TUI_SERVER_TOKEN ?? '';
  if (!token) {
    // Fail closed: never start unauthenticated. Print a one-time token the
    // operator can persist as TUI_SERVER_TOKEN.
    token = randomBytes(32).toString('hex');
    console.error('TUI_SERVER_TOKEN is not set — refusing to start without it.');
    console.error('Generate one and retry, e.g.:');
    console.error(`  TUI_SERVER_TOKEN=${token} node dist/server.js`);
    console.error('(Save that token somewhere safe — it will not be shown again.)');
    process.exit(1);
  }

  let config;
  try {
    config = loadConfig({}, SYSTEM_PROMPT);
  } catch (err) {
    console.error(`✗ ${(err as Error).message}`);
    process.exit(1);
  }

  const corsOrigins = (process.env.TUI_CORS_ORIGINS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  startServer({
    config,
    token,
    host: process.env.TUI_HOST ?? '127.0.0.1',
    port: Number(process.env.TUI_PORT ?? '8787'),
    corsOrigins,
    version: version(),
  });
}

main();
