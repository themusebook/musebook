import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

export interface LoaderConfig {
  text: string;
  style: 'gradient' | 'spinner' | 'minimal';
}

export interface DisplayConfig {
  toolDisplay: 'grouped' | 'emoji' | 'minimal' | 'hidden';
  inputStyle: 'block' | 'bordered' | 'plain';
  loader: LoaderConfig;
}

export interface AgentConfig {
  apiKey: string;
  model: string;
  systemPrompt: string;
  maxSteps: number;
  maxCost: number;
  mcpUrl: string;
  sessionDir: string;
  showBanner: boolean;
  display: DisplayConfig;
  slashCommands: boolean;
}

export const FREE_ROUTER_MODEL = 'openrouter/free';

const DEFAULTS: Omit<AgentConfig, 'apiKey' | 'systemPrompt'> = {
  model: FREE_ROUTER_MODEL,
  maxSteps: 50,
  maxCost: 1.0,
  mcpUrl: 'https://musebook.trade/mcp',
  sessionDir: join(homedir(), '.musebook', 'tui', 'sessions'),
  showBanner: true,
  display: {
    toolDisplay: 'grouped',
    inputStyle: 'block',
    loader: { text: 'Thinking', style: 'gradient' },
  },
  slashCommands: true,
};

export function loadConfig(
  overrides: Partial<AgentConfig> = {},
  systemPrompt: string,
): AgentConfig {
  let base = { ...DEFAULTS };

  const configPath = resolve('agent.config.json');
  if (existsSync(configPath)) {
    try {
      const file = JSON.parse(readFileSync(configPath, 'utf-8'));
      if (file.display) base.display = { ...base.display, ...file.display };
      const { display: _d, ...rest } = file;
      base = { ...base, ...rest, display: base.display };
    } catch {
      // malformed config file — fall back to defaults
    }
  }

  if (process.env.AGENT_MODEL) base.model = process.env.AGENT_MODEL;
  if (process.env.AGENT_MAX_STEPS) base.maxSteps = Number(process.env.AGENT_MAX_STEPS);
  if (process.env.AGENT_MAX_COST) base.maxCost = Number(process.env.AGENT_MAX_COST);
  if (process.env.MUSEBOOK_MCP_URL) base.mcpUrl = process.env.MUSEBOOK_MCP_URL;

  const apiKey = process.env.OPENROUTER_API_KEY ?? '';
  if (!apiKey) {
    throw new Error(
      'OPENROUTER_API_KEY is required. Get one at https://openrouter.ai/settings/keys ' +
        'and export OPENROUTER_API_KEY=<key>. The TUI defaults to the free model router ($0).',
    );
  }

  let display = { ...base.display, ...(overrides.display ?? {}) };
  const { display: _od, ...restOverrides } = overrides;
  return { ...base, ...restOverrides, display, apiKey, systemPrompt };
}

export function isFreeModel(model: string): boolean {
  return model === FREE_ROUTER_MODEL || model.endsWith(':free');
}

/** Minimal .env loader — no dependency, only fills vars that are not already set. */
export function loadDotEnv(path = '.env'): void {
  if (!existsSync(path)) return;
  for (const line of readFileSync(path, 'utf-8').split('\n')) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2];
  }
}
