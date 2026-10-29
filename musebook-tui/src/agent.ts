import { OpenRouter, serverTool, stepCountIs, maxCost, isMcpTool } from '@openrouter/agent';
import type { Item, StateAccessor } from '@openrouter/agent';
import type { AgentConfig } from './config.js';
import { musebookTools } from './tools/musebook.js';
import { actionTools } from './tools/actions.js';
import { appendJsonl } from './session.js';
import { withMcpUrl } from './mcp.js';

export type AgentEvent =
  | { type: 'text'; delta: string }
  | { type: 'tool_call'; name: string; callId: string; args: Record<string, unknown> }
  | { type: 'tool_result'; name: string; callId: string; output: string }
  | { type: 'tool_progress'; name: string; progress: number; message: string };

export interface PendingCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface RunResult {
  text: string;
  status: string;
  pendingCalls: PendingCall[];
  usage: { inputTokens: number; outputTokens: number; cost: number };
  routedModel?: string;
}

const tools = [
  ...musebookTools,
  ...actionTools,
  serverTool({ type: 'openrouter:web_search' }),
  serverTool({ type: 'openrouter:datetime', parameters: { timezone: 'UTC' } }),
];

export function listTools(): Array<{ name: string; description: string; mcp: boolean }> {
  return tools.map((t) => {
    const branded = t as { _brand?: string; id?: string; function?: { name?: string; description?: string } };
    if (branded._brand === 'server-tool') {
      return {
        name: branded.id ?? 'server-tool',
        description: 'OpenRouter server tool',
        mcp: false,
      };
    }
    const fn = branded.function ?? {};
    return {
      name: fn.name ?? 'unknown',
      description: fn.description ?? '',
      mcp: isMcpTool(t as never),
    };
  });
}

export function runAgent(
  config: AgentConfig,
  input: string | Item[],
  state: StateAccessor,
  options?: { onEvent?: (event: AgentEvent) => void; jsonlPath?: string },
): Promise<RunResult> {
  return withMcpUrl(config.mcpUrl, () => runConfiguredAgent(config, input, state, options));
}

async function runConfiguredAgent(
  config: AgentConfig,
  input: string | Item[],
  state: StateAccessor,
  options?: {
    onEvent?: (event: AgentEvent) => void;
    jsonlPath?: string;
  },
): Promise<RunResult> {
  const client = new OpenRouter({ apiKey: config.apiKey });
  const onEvent = options?.onEvent;

  const result = client.callModel({
    model: config.model,
    instructions: config.systemPrompt,
    input,
    tools: tools as never,
    stopWhen: [stepCountIs(config.maxSteps), maxCost(config.maxCost)],
    state: state as never,
  });

  const callNames = new Map<string, string>();
  const done = new Promise<void>((resolve) => {
    (async () => {
      try {
        const textP = (async () => {
          if (!onEvent) return;
          for await (const delta of result.getTextStream()) {
            if (delta) onEvent({ type: 'text', delta });
          }
        })();
        const callsP = (async () => {
          if (!onEvent) return;
          for await (const call of result.getToolCallsStream()) {
            callNames.set(call.id, call.name);
            onEvent({
              type: 'tool_call',
              name: call.name,
              callId: call.id,
              args: (call.arguments ?? {}) as Record<string, unknown>,
            });
          }
        })();
        const resultsP = (async () => {
          if (!onEvent) return;
          for await (const item of result.getItemsStream()) {
            const it = item as {
              type?: string;
              call_id?: string;
              output?: unknown;
            };
            if (it.type === 'function_call_output') {
              const out =
                typeof it.output === 'string' ? it.output : JSON.stringify(it.output ?? '');
              onEvent({
                type: 'tool_result',
                name: (it.call_id && callNames.get(it.call_id)) || 'tool',
                callId: it.call_id ?? '',
                output: out.length > 300 ? out.slice(0, 300) + '…' : out,
              });
            }
          }
        })();
        const progressP = (async () => {
          if (!onEvent) return;
          for await (const ev of result.getToolStream()) {
            const e = ev as {
              type: string;
              toolCallId?: string;
              result?: { progress?: number; message?: string };
            };
            if (e.type === 'preliminary_result' && e.result) {
              onEvent({
                type: 'tool_progress',
                name: (e.toolCallId && callNames.get(e.toolCallId)) || 'tool',
                progress: e.result.progress ?? 0,
                message: e.result.message ?? '',
              });
            }
          }
        })();
        await Promise.all([textP, callsP, resultsP, progressP]);
      } finally {
        resolve();
      }
    })();
  });

  const response = await result.getResponse();
  await done;
  const snapshot = await result.getState();

  const pending: PendingCall[] =
    snapshot.status === 'awaiting_hitl'
      ? (await result.getPendingToolCalls()).map((c) => ({
          id: c.id,
          name: c.name,
          arguments: (c.arguments ?? {}) as Record<string, unknown>,
        }))
      : [];

  const usage = (response as { usage?: Record<string, number> }).usage ?? {};
  const routedModel =
    (response as { model?: string }).model ?? (response as { provider?: string }).provider;
  const run: RunResult = {
    text: await result.getText(),
    status: snapshot.status,
    pendingCalls: pending,
    usage: {
      inputTokens: usage.inputTokens ?? usage.input_tokens ?? 0,
      outputTokens: usage.outputTokens ?? usage.output_tokens ?? 0,
      cost: usage.cost ?? 0,
    },
    routedModel,
  };

  if (options?.jsonlPath && run.text) {
    appendJsonl(options.jsonlPath, { role: 'assistant', content: run.text });
  }
  return run;
}
