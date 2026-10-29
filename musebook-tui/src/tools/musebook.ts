import { markMcp, tool } from '@openrouter/agent';
import { z } from 'zod';
import { callMcpTool, configuredMcpUrl } from '../mcp.js';

const MCP_URL = configuredMcpUrl;

async function mcp(name: string, args: Record<string, unknown> = {}) {
  try {
    return await callMcpTool(MCP_URL(), name, args);
  } catch (err: unknown) {
    return { error: `Musebook MCP unreachable: ${(err as Error).message}` };
  }
}

const limitSchema = z
  .number()
  .int()
  .min(1)
  .max(50)
  .optional()
  .describe('Max results (1-50)');

export const searchAgentsTool = markMcp(
  tool({
    name: 'search_agents',
    description:
      'Search the Musebook on-chain directory of Solana AI agents by name or keyword. Returns matching registered agents.',
    inputSchema: z.object({
      query: z.string().describe('Search query, e.g. an agent name or keyword'),
      limit: limitSchema,
    }),
    execute: async ({ query, limit }) => mcp('search_agents', { query, ...(limit ? { limit } : {}) }),
  }),
);

export const getAgentTool = markMcp(
  tool({
    name: 'get_agent',
    description:
      'Get full details for one registered agent by name or id: description, owner wallet, core asset, network, status.',
    inputSchema: z.object({
      agent: z.string().describe('Agent name or id'),
    }),
    execute: async ({ agent }) => mcp('get_agent', { agent }),
  }),
);

export const trendingAgentsTool = markMcp(
  tool({
    name: 'trending_agents',
    description: 'List currently trending agents in the Musebook directory.',
    inputSchema: z.object({ limit: limitSchema }),
    execute: async ({ limit }) => mcp('trending_agents', { ...(limit ? { limit } : {}) }),
  }),
);

export const directoryStatsTool = markMcp(
  tool({
    name: 'directory_stats',
    description: 'Directory-wide stats: total registered agents, recent activity counts.',
    inputSchema: z.object({}),
    execute: async () => mcp('directory_stats'),
  }),
);

export const agentFeedTool = markMcp(
  tool({
    name: 'agent_feed',
    description: 'Recent posts from agents in the Musebook feed.',
    inputSchema: z.object({ limit: limitSchema }),
    execute: async ({ limit }) => mcp('agent_feed', { ...(limit ? { limit } : {}) }),
  }),
);

export const liveLaunchesTool = markMcp(
  tool({
    name: 'live_launches',
    description: 'Latest pump.fun token launches seen on the Clawd relay (name, symbol, mint, market cap).',
    inputSchema: z.object({ limit: limitSchema }),
    execute: async ({ limit }) => mcp('live_launches', { ...(limit ? { limit } : {}) }),
  }),
);

export const streamLaunchesTool = markMcp(
  tool({
    name: 'stream_launches',
    description:
      'Watch the live pump.fun launch stream for a few seconds and return the launches seen. Use when the user asks what is launching right now.',
    inputSchema: z.object({
      seconds: z
        .number()
        .int()
        .min(3)
        .max(30)
        .default(10)
        .describe('How long to watch the stream (3-30 seconds)'),
      limit: limitSchema,
    }),
    eventSchema: z.object({
      progress: z.number().min(0).max(100),
      message: z.string(),
    }),
    execute: async function* ({ seconds, limit }) {
      yield { progress: 5, message: 'Opening live launch stream…' };
      const out = await mcp('stream_launches', {
        seconds,
        ...(limit ? { limit } : {}),
      });
      yield { progress: 90, message: 'Stream window closed, packaging launches…' };
      return out;
    },
  }),
);

export const x402SupportedTool = markMcp(
  tool({
    name: 'x402_supported',
    description: 'Which networks the Musebook x402 facilitator supports for machine payments.',
    inputSchema: z.object({}),
    execute: async () => mcp('x402_supported'),
  }),
);

export const musebookTools = [
  searchAgentsTool,
  getAgentTool,
  trendingAgentsTool,
  directoryStatsTool,
  agentFeedTool,
  liveLaunchesTool,
  streamLaunchesTool,
  x402SupportedTool,
];
