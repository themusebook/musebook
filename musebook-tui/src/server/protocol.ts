import type { ServerResponse } from 'node:http';
import type { AgentEvent } from '../agent.js';

/** Events streamed to SSE clients, as JSON payloads. */
export type ServerEvent =
  | { type: 'ready'; session_id: string }
  | { type: 'text'; delta: string }
  | { type: 'tool_call'; name: string; call_id: string; args: Record<string, unknown> }
  | { type: 'tool_result'; name: string; call_id: string; output: string }
  | { type: 'tool_progress'; name: string; progress: number; message: string }
  | {
      type: 'approval_required';
      call_id: string;
      tool: string;
      args: Record<string, unknown>;
      heading: string;
      detail: string[];
      reason: string;
    }
  | { type: 'approval_resolved'; call_id: string; approved: boolean; auto?: boolean }
  | {
      type: 'done';
      status: string;
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
      model: string;
      routed_model?: string;
    }
  | { type: 'error'; message: string };

export function agentEventToServer(e: AgentEvent): ServerEvent {
  switch (e.type) {
    case 'text':
      return { type: 'text', delta: e.delta };
    case 'tool_call':
      return { type: 'tool_call', name: e.name, call_id: e.callId, args: e.args };
    case 'tool_result':
      return { type: 'tool_result', name: e.name, call_id: e.callId, output: e.output };
    case 'tool_progress':
      return { type: 'tool_progress', name: e.name, progress: e.progress, message: e.message };
  }
}

export function openSse(res: ServerResponse, sessionId: string): void {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  sendSse(res, { type: 'ready', session_id: sessionId });
}

export function sendSse(res: ServerResponse, event: ServerEvent): void {
  res.write(`data: ${JSON.stringify(event)}\n\n`);
}
