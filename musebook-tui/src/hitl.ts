import type { StateAccessor } from '@openrouter/agent';
import type { AgentConfig } from './config.js';
import { runAgent, type PendingCall, type RunResult } from './agent.js';
import { resumeLoop, type Decider } from './approvals.js';
import type { Prompter } from './prompter.js';

const RESET = '\x1b[0m';
const DIM = '\x1b[2m';
const BOLD = '\x1b[1m';
const YELLOW = '\x1b[38;5;220m';

function divider(): string {
  return `${DIM}${'─'.repeat(56)}${RESET}`;
}

/**
 * CLI human-in-the-loop: present each paused tool call with its original
 * arguments, ask y/N, and resume. Thin wrapper over the shared approval
 * core (approvals.ts) — the HTTP server reuses the same core with an SSE
 * decider instead of a terminal prompt.
 */
export async function handleHitl(
  prompter: Prompter,
  config: AgentConfig,
  calls: PendingCall[],
  state: StateAccessor,
  events: {
    onEvent: NonNullable<Parameters<typeof runAgent>[3]>['onEvent'];
    jsonlPath?: string;
  },
): Promise<RunResult> {
  const decider: Decider = async (req) => {
    console.log();
    console.log(divider());
    console.log(`  ${BOLD}${YELLOW}⏸ Approval needed — ${req.heading}${RESET}`);
    console.log(divider());
    for (const line of req.detail) {
      if (line) console.log(`  ${DIM}${line}${RESET}`);
    }
    console.log(`  ${DIM}call ${req.id} · args unchanged${RESET}`);
    const answer = (await prompter.ask(`  Approve? [y/N] `)).trim().toLowerCase();
    const approved = answer === 'y' || answer === 'yes';
    console.log(divider());
    return approved;
  };

  return resumeLoop(config, calls, state, decider, {
    onEvent: events.onEvent,
    jsonlPath: events.jsonlPath,
  });
}
