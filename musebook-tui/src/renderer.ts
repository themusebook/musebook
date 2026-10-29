// Grouped tool display: each tool family gets its own color and marker so a
// busy run stays scannable. Mirrors the skill's `toolDisplay: 'grouped'` mode.

const RESET = '\x1b[0m';
const DIM = '\x1b[2m';
const GREEN = '\x1b[38;5;84m';
const PURPLE = '\x1b[38;5;135m';
const YELLOW = '\x1b[38;5;220m';
const CYAN = '\x1b[38;5;87m';

const MUSEBOOK_TOOLS = new Set([
  'search_agents',
  'get_agent',
  'trending_agents',
  'directory_stats',
  'agent_feed',
  'live_launches',
  'stream_launches',
  'x402_supported',
]);

const ACTION_TOOLS = new Set(['open_in_browser', 'save_note', 'draft_agent_registration']);

function colorFor(name: string): string {
  if (MUSEBOOK_TOOLS.has(name)) return PURPLE;
  if (ACTION_TOOLS.has(name)) return YELLOW;
  return CYAN;
}

const startTimes = new Map<string, number>();

function summarizeArgs(args: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    const s = typeof v === 'string' ? v : JSON.stringify(v);
    parts.push(`${k}=${s.length > 40 ? s.slice(0, 40) + '…' : s}`);
  }
  return parts.join(' ');
}

export function renderToolCall(name: string, callId: string, args: Record<string, unknown>): void {
  startTimes.set(callId, Date.now());
  const color = colorFor(name);
  const summary = summarizeArgs(args);
  process.stdout.write(`\r\x1b[K  ${color}⚡ ${name}${RESET}${summary ? ` ${DIM}${summary}${RESET}` : ''}\n`);
}

export function renderToolProgress(name: string, progress: number, message: string): void {
  const bar = '█'.repeat(Math.round(progress / 10)) + '░'.repeat(10 - Math.round(progress / 10));
  process.stdout.write(`\r\x1b[K  ${PURPLE}${bar} ${progress}% ${message}${RESET}`);
}

export function renderToolResult(name: string, callId: string, output: string): void {
  const started = startTimes.get(callId);
  const ms = started ? ` (${((Date.now() - started) / 1000).toFixed(1)}s)` : '';
  process.stdout.write(`\r\x1b[K  ${GREEN}✓ ${name}${RESET}${DIM}${ms}${RESET}\n`);
  const preview = output.split('\n').slice(0, 3).join('\n');
  if (preview.trim()) {
    for (const line of preview.split('\n')) {
      process.stdout.write(`    ${DIM}${line.slice(0, 100)}${RESET}\n`);
    }
  }
}

export function renderError(message: string): void {
  process.stdout.write(`\r\x1b[K  \x1b[38;5;196m✗ ${message}${RESET}\n`);
}
