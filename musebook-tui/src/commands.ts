import { writeFileSync } from 'node:fs';
import { OpenRouter, maxCost } from '@openrouter/agent';
import type { AgentConfig } from './config.js';
import type { Prompter } from './prompter.js';
import { FREE_ROUTER_MODEL, isFreeModel } from './config.js';
import { listTools } from './agent.js';
import { fetchModels, per1M, type ModelInfo } from './models.js';
import { fileStateAccessor, newSession, readTranscript } from './session.js';

const RESET = '\x1b[0m';
const DIM = '\x1b[2m';
const BOLD = '\x1b[1m';
const GREEN = '\x1b[38;5;84m';
const PURPLE = '\x1b[38;5;135m';
const YELLOW = '\x1b[38;5;220m';

export interface Totals {
  inputTokens: number;
  outputTokens: number;
  cost: number;
}

export interface SessionHandle {
  id: string;
  jsonlPath: string;
  statePath: string;
}

export interface CommandContext {
  config: AgentConfig;
  prompter: Prompter;
  messages: Array<{ role: string; content: string }>;
  session: SessionHandle;
  totals: Totals;
  resetSession: () => void;
  setModel: (model: string) => void;
}

type Handler = (ctx: CommandContext, args: string) => Promise<void>;

const helpText = [
  `${BOLD}Commands${RESET}`,
  `  ${PURPLE}/model [search]${RESET}  switch model — pricing shown before any paid switch`,
  `  ${PURPLE}/free${RESET}            back to the free router (openrouter/free)`,
  `  ${PURPLE}/tools${RESET}           list available tools`,
  `  ${PURPLE}/cost${RESET}            session token + spend totals`,
  `  ${PURPLE}/session${RESET}         session file, message count, model`,
  `  ${PURPLE}/export [path]${RESET}   save transcript as markdown`,
  `  ${PURPLE}/compact${RESET}         summarize history and start a fresh session`,
  `  ${PURPLE}/new${RESET}             start a fresh session`,
  `  ${PURPLE}/help${RESET}            this list`,
  `  ${PURPLE}/quit${RESET}            exit`,
  ``,
  `${DIM}Action tools (open_in_browser, save_note) pause for your approval.`,
  `Routine Musebook lookups run free and uninterrupted.${RESET}`,
].join('\n');

const commands: Record<string, Handler> = {
  help: async () => {
    console.log(helpText);
  },

  free: async (ctx) => {
    ctx.setModel(FREE_ROUTER_MODEL);
    console.log(`  ${GREEN}✓${RESET} model → ${BOLD}${FREE_ROUTER_MODEL}${RESET} ${DIM}(free)${RESET}`);
  },

  tools: async () => {
    console.log(`  ${BOLD}Tools${RESET}`);
    for (const t of listTools()) {
      const badge = t.mcp ? ` ${DIM}[mcp]${RESET}` : '';
      console.log(`  ${PURPLE}⚡${RESET} ${t.name}${badge} ${DIM}— ${t.description.slice(0, 72)}${RESET}`);
    }
  },

  cost: async (ctx) => {
    const t = ctx.totals;
    console.log(
      `  ${BOLD}Session spend${RESET}  ${t.inputTokens.toLocaleString()} in / ${t.outputTokens.toLocaleString()} out  ·  $${t.cost.toFixed(4)}`,
    );
    if (isFreeModel(ctx.config.model)) {
      console.log(`  ${DIM}on ${ctx.config.model} — inference is free; only Jev gates add fractions of a cent.${RESET}`);
    }
  },

  session: async (ctx) => {
    console.log(`  ${BOLD}Session${RESET}  ${ctx.session.id}`);
    console.log(`  model    ${ctx.config.model}`);
    console.log(`  messages ${ctx.messages.length}`);
    console.log(`  log      ${ctx.session.jsonlPath}`);
  },

  new: async (ctx) => {
    ctx.resetSession();
    console.log(`  ${GREEN}✓${RESET} fresh session started ${DIM}(${ctx.session.id})${RESET}`);
  },

  export: async (ctx, args) => {
    const path = args.trim() || `musebook-tui-${ctx.session.id}.md`;
    const rows = readTranscript(ctx.session.jsonlPath);
    const md = [
      `# Musebook TUI — ${ctx.session.id}`,
      ``,
      `_model: ${ctx.config.model} · exported ${new Date().toISOString()}_`,
      ``,
      ...rows.flatMap((r) => [`## ${r.role}`, ``, r.content, ``]),
    ].join('\n');
    writeFileSync(path, md, 'utf-8');
    console.log(`  ${GREEN}✓${RESET} exported ${rows.length} messages → ${BOLD}${path}${RESET}`);
  },

  model: async (ctx, args) => {
    console.log(`  ${DIM}searching models…${RESET}`);
    let models: ModelInfo[];
    try {
      models = await fetchModels(ctx.config.apiKey);
    } catch (err) {
      console.log(`  ✗ model search failed: ${(err as Error).message}`);
      return;
    }
    const q = args.trim().toLowerCase();
    const hits = models
      .filter((m) => !q || m.id.toLowerCase().includes(q) || (m.name ?? '').toLowerCase().includes(q))
      .slice(0, 10);
    if (hits.length === 0) {
      console.log(`  no models match "${args.trim()}"`);
      return;
    }
    console.log(`  ${BOLD}Models${RESET} ${DIM}(price per 1M tokens in/out)${RESET}`);
    hits.forEach((m, i) => {
      const free = m.id === FREE_ROUTER_MODEL || m.id.endsWith(':free');
      const price = free
        ? `${GREEN}free${RESET}`
        : `${per1M(m.pricing?.prompt)} / ${per1M(m.pricing?.completion)}`;
      const current = m.id === ctx.config.model ? ` ${YELLOW}← current${RESET}` : '';
      console.log(`  [${i}] ${m.id}${current}  ${DIM}${price}${RESET}`);
    });
    const answer = await ctx.prompter.ask(`  pick a number, or Enter to cancel: `);
    const n = Number(answer.trim());
    if (!Number.isInteger(n) || n < 0 || n >= hits.length) {
      console.log(`  ${DIM}cancelled${RESET}`);
      return;
    }
    const picked = hits[n]!;
    if (!isFreeModel(picked.id)) {
      const confirm = await ctx.prompter.ask(
        `  ${YELLOW}⚠ ${picked.id} is PAID (${per1M(picked.pricing?.prompt)} in / ${per1M(picked.pricing?.completion)} out per 1M). Switch? [y/N]${RESET} `,
      );
      if (!['y', 'yes'].includes(confirm.trim().toLowerCase())) {
        console.log(`  ${DIM}cancelled${RESET}`);
        return;
      }
    }
    ctx.setModel(picked.id);
    console.log(`  ${GREEN}✓${RESET} model → ${BOLD}${picked.id}${RESET}`);
  },

  compact: async (ctx) => {
    if (ctx.messages.length === 0) {
      console.log(`  ${DIM}nothing to compact${RESET}`);
      return;
    }
    console.log(`  ${DIM}summarizing ${ctx.messages.length} messages…${RESET}`);
    const client = new OpenRouter({ apiKey: ctx.config.apiKey });
    const transcript = ctx.messages
      .map((m) => `${m.role.toUpperCase()}: ${m.content}`)
      .join('\n\n')
      .slice(0, 12000);
    try {
      const res = await client.callModel({
        model: FREE_ROUTER_MODEL,
        instructions:
          'Summarize this conversation into a compact brief: key facts established, tools used and what they returned, open questions, and the user\'s current goal. Keep it under 400 words.',
        input: transcript,
        stopWhen: [maxCost(0.05)],
      });
      const summary = await res.getText();
      const prevId = ctx.session.id;
      ctx.resetSession();
      ctx.messages.push({
        role: 'user',
        content: `[Continuing from compacted session ${prevId}. Summary: ${summary}]`,
      });
      console.log(`  ${GREEN}✓${RESET} compacted ${DIM}(was ${prevId}, now ${ctx.session.id})${RESET}`);
    } catch (err) {
      console.log(`  ✗ compact failed: ${(err as Error).message}`);
    }
  },
};

export function isCommand(line: string): boolean {
  return line.startsWith('/');
}

export async function runCommand(ctx: CommandContext, line: string): Promise<boolean> {
  const [raw, ...rest] = line.slice(1).split(' ');
  const name = (raw ?? '').toLowerCase();
  if (name === 'quit' || name === 'exit') return false;
  const handler = commands[name];
  if (!handler) {
    console.log(`  unknown command /${name} — try /help`);
    return true;
  }
  await handler(ctx, rest.join(' '));
  return true;
}

export function makeSessionHandle(config: AgentConfig): SessionHandle {
  const { jsonlPath, statePath, meta } = newSession(config.sessionDir);
  void meta;
  const id = jsonlPath.split('/').pop()!.replace('.jsonl', '');
  return { id, jsonlPath, statePath };
}

export function makeStateAccessor(handle: SessionHandle) {
  return fileStateAccessor(handle.statePath);
}
