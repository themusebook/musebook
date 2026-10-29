#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { fileStateAccessor, newSession, appendJsonl } from './session.js';
import { createPrompter } from './prompter.js';
import { loadConfig, loadDotEnv, type AgentConfig } from './config.js';
import { printBanner } from './banner.js';
import { Loader } from './loader.js';
import { runAgent, type AgentEvent, type RunResult } from './agent.js';
import { renderToolCall, renderToolResult, renderToolProgress, renderError } from './renderer.js';
import { handleHitl } from './hitl.js';
import { getMcpConnection, closeMcp } from './mcp.js';
import { SYSTEM_PROMPT } from './system-prompt.js';
import {
  isCommand,
  runCommand,
  type CommandContext,
  type SessionHandle,
  type Totals,
} from './commands.js';

const VERSION = '0.1.2';
const RESET = '\x1b[0m';
const DIM = '\x1b[2m';
const BOLD = '\x1b[1m';

function printTurnFooter(run: RunResult, model: string): void {
  const u = run.usage;
  const routed = (run as { routedModel?: string }).routedModel;
  const modelNote =
    routed && routed !== model ? ` · routed ${routed}` : ``;
  console.log(
    `${DIM}  ─ ${u.inputTokens.toLocaleString()} in / ${u.outputTokens.toLocaleString()} out · $${u.cost.toFixed(4)} · ${model}${modelNote}${RESET}`,
  );
}

async function main(): Promise<void> {
  loadDotEnv();

  let config: AgentConfig;
  try {
    config = loadConfig({}, SYSTEM_PROMPT);
  } catch (err) {
    console.error(`\n  ✗ ${(err as Error).message}\n`);
    process.exit(1);
  }

  if (config.showBanner) printBanner(config.model, VERSION);

  // Session (fresh each launch; resume by pointing at an existing state file).
  let session: SessionHandle = (() => {
    const { jsonlPath, statePath } = newSession(config.sessionDir);
    return { id: jsonlPath.split('/').pop()!.replace('.jsonl', ''), jsonlPath, statePath };
  })();
  let state = fileStateAccessor(session.statePath);

  const messages: Array<{ role: string; content: string }> = [];
  const totals: Totals = { inputTokens: 0, outputTokens: 0, cost: 0 };

  // Warm up the Musebook MCP connection so first-tool latency is honest.
  try {
    const { client } = await getMcpConnection(config.mcpUrl);
    const listed = await client.listTools();
    console.log(
      `  ${DIM}connected to Musebook MCP · ${listed.tools.length} remote tools · ${config.mcpUrl}${RESET}`,
    );
  } catch (err) {
    console.log(
      `  ${DIM}⚠ Musebook MCP unreachable (${(err as Error).message}) — directory tools will report errors${RESET}`,
    );
  }

  const prompter = createPrompter();
  const rl = prompter.rl;

  let sigints = 0;
  rl.on('SIGINT', () => {
    sigints++;
    if (sigints >= 2) {
      console.log('\n  bye 🦞');
      process.exit(0);
    }
    console.log(`\n  ${DIM}press Ctrl+C again to exit, or /quit${RESET}`);
  });

  const loader = new Loader(config.display.loader);

  const onEvent = (event: AgentEvent) => {
    if (loader.running) {
      loader.stop();
      process.stdout.write('\n');
    }
    switch (event.type) {
      case 'text':
        process.stdout.write(event.delta);
        break;
      case 'tool_call':
        renderToolCall(event.name, event.callId, event.args);
        break;
      case 'tool_result':
        renderToolResult(event.name, event.callId, event.output);
        break;
      case 'tool_progress':
        renderToolProgress(event.name, event.progress, event.message);
        break;
    }
  };

  const promptLine = () => {
    console.log();
    console.log(`${DIM}┌─ ask musebook  (/help for commands)${RESET}`);
    process.stdout.write(`${DIM}└─${RESET} 🦞 `);
  };

  const ctx: CommandContext = {
    config,
    prompter,
    messages,
    get session() {
      return session;
    },
    totals,
    resetSession: () => {
      const { jsonlPath, statePath } = newSession(config.sessionDir);
      session = {
        id: jsonlPath.split('/').pop()!.replace('.jsonl', ''),
        jsonlPath,
        statePath,
      };
      state = fileStateAccessor(session.statePath);
      messages.length = 0;
    },
    setModel: (model: string) => {
      config.model = model;
    },
  };

  console.log(`  ${DIM}session ${session.id} · state persists across restarts${RESET}`);

  const askOnce = async (): Promise<string> => {
    promptLine();
    return prompter.ask();
  };

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const line = (await askOnce()).trim();
    sigints = 0;
    if (!line) continue;

    if (isCommand(line)) {
      const keepGoing = await runCommand(ctx, line);
      if (!keepGoing) break;
      continue;
    }

    messages.push({ role: 'user', content: line });
    appendJsonl(session.jsonlPath, { role: 'user', content: line });

    loader.start();
    let run: RunResult;
    try {
      run = await runAgent(config, line, state, { onEvent, jsonlPath: session.jsonlPath });
    } catch (err) {
      loader.stop();
      renderError((err as Error).message);
      continue;
    } finally {
      if (loader.running) loader.stop();
    }
    console.log();

    if (run.status === 'awaiting_hitl' && run.pendingCalls.length > 0) {
      try {
        run = await handleHitl(prompter, config, run.pendingCalls, state, {
          onEvent,
          jsonlPath: session.jsonlPath,
        });
      } catch (err) {
        renderError((err as Error).message);
        continue;
      }
      console.log();
    } else if (run.status !== 'complete' && run.status !== 'awaiting_hitl') {
      console.log(`  ${DIM}run stopped: ${run.status}${RESET}`);
    }

    if (run.text) {
      messages.push({ role: 'assistant', content: run.text });
    }
    totals.inputTokens += run.usage.inputTokens;
    totals.outputTokens += run.usage.outputTokens;
    totals.cost += run.usage.cost;
    printTurnFooter(run, config.model);
  }

  prompter.close();
  await closeMcp();
  console.log(`\n  bye 🦞  ${DIM}session saved to ${session.jsonlPath}${RESET}`);
}

main().catch((err) => {
  console.error(`\n  ✗ fatal: ${(err as Error).message}`);
  process.exit(1);
});
