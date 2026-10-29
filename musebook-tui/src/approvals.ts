import type { Item, StateAccessor } from '@openrouter/agent';
import type { AgentConfig } from './config.js';
import { runAgent, type PendingCall, type RunResult } from './agent.js';

/**
 * Shared human-in-the-loop core for the CLI and the HTTP/SSE server.
 *
 * A Decider answers one question per paused tool call: approve or deny.
 * The original arguments are shown unchanged — the reviewer never edits
 * them, they only decide. The resume output shapes below must match what
 * each tool's `onResponseReceived` parses (see tools/actions.ts).
 */
export interface ApprovalRequest {
  id: string;
  name: string;
  args: Record<string, unknown>;
  heading: string;
  detail: string[];
}

export type Decider = (req: ApprovalRequest) => Promise<boolean>;

export function summarizeCall(call: PendingCall): { heading: string; detail: string[] } {
  if (call.name === 'open_in_browser') {
    const url = String(call.arguments.url ?? '');
    const reason = call.arguments.reason ? String(call.arguments.reason) : '';
    return {
      heading: 'Open in browser',
      detail: [url, ...(reason ? [reason] : [])],
    };
  }
  if (call.name === 'save_note') {
    const title = String(call.arguments.title ?? '');
    const body = String(call.arguments.body ?? '');
    return {
      heading: `Save note: ${title}`,
      detail: body.split('\n').slice(0, 8).map((l) => l.slice(0, 120)),
    };
  }
  return {
    heading: `Approve ${call.name}?`,
    detail: [JSON.stringify(call.arguments)],
  };
}

function resumeItemFor(call: PendingCall, approved: boolean): Item {
  let output: string;
  if (call.name === 'open_in_browser') {
    output = JSON.stringify({ approved, url: String(call.arguments.url ?? '') });
  } else if (call.name === 'save_note') {
    // The SDK hands onResponseReceived only the resume output, never the
    // original call arguments — so the approval re-embeds title/body exactly
    // as the model produced them. The reviewer cannot edit them here.
    output = JSON.stringify({
      decision: approved ? 'approve' : 'deny',
      title: String(call.arguments.title ?? ''),
      body: String(call.arguments.body ?? ''),
    });
  } else {
    output = JSON.stringify({ approved });
  }
  return { type: 'function_call_output', callId: call.id, output } as never;
}

/** Ask the decider about every paused call, in order. */
export async function collectDecisions(
  calls: PendingCall[],
  decider: Decider,
): Promise<Item[]> {
  const items: Item[] = [];
  for (const call of calls) {
    const { heading, detail } = summarizeCall(call);
    const approved = await decider({ id: call.id, name: call.name, args: call.arguments, heading, detail });
    items.push(resumeItemFor(call, approved));
  }
  return items;
}

export interface ResumeOptions {
  onEvent: NonNullable<Parameters<typeof runAgent>[3]>['onEvent'];
  jsonlPath?: string;
}

/**
 * Resolve one round of paused calls with the decider, resume the run, and
 * keep going while the model keeps pausing for approval.
 */
export async function resumeLoop(
  config: AgentConfig,
  calls: PendingCall[],
  state: StateAccessor,
  decider: Decider,
  opts: ResumeOptions,
): Promise<RunResult> {
  let pending = calls;
  for (;;) {
    const items = await collectDecisions(pending, decider);
    const run = await runAgent(config, items, state, {
      onEvent: opts.onEvent,
      jsonlPath: opts.jsonlPath,
    });
    if (run.status !== 'awaiting_hitl' || run.pendingCalls.length === 0) return run;
    pending = run.pendingCalls;
  }
}
