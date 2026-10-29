import type { ServerResponse } from 'node:http';
import type { StateAccessor } from '@openrouter/agent';
import type { AgentConfig } from '../config.js';
import { runAgent, type AgentEvent, type RunResult } from '../agent.js';
import { resumeLoop, type Decider } from '../approvals.js';
import { fileStateAccessor, newSession, appendJsonl } from '../session.js';
import { agentEventToServer, sendSse, type ServerEvent } from './protocol.js';

export interface ServerSession {
  id: string;
  createdAt: string;
  /** per-session copy of the config — model switches stay local to the session */
  config: AgentConfig;
  state: StateAccessor;
  jsonlPath: string;
  transcript: Array<{ role: string; content: string }>;
  totals: { inputTokens: number; outputTokens: number; cost: number };
  clients: Set<ServerResponse>;
  queue: Promise<void>;
  approvals: Map<string, (approved: boolean) => void>;
  running: boolean;
}

/** Approvals left hanging this long are auto-denied. */
const APPROVAL_TIMEOUT_MS = 5 * 60 * 1000;

export class SessionManager {
  private sessions = new Map<string, ServerSession>();

  constructor(private baseConfig: AgentConfig) {}

  create(model?: string): ServerSession {
    const { jsonlPath, statePath } = newSession(this.baseConfig.sessionDir);
    const id = jsonlPath.split('/').pop()!.replace('.jsonl', '');
    const session: ServerSession = {
      id,
      createdAt: new Date().toISOString(),
      config: { ...this.baseConfig, ...(model ? { model } : {}) },
      state: fileStateAccessor(statePath),
      jsonlPath,
      transcript: [],
      totals: { inputTokens: 0, outputTokens: 0, cost: 0 },
      clients: new Set(),
      queue: Promise.resolve(),
      approvals: new Map(),
      running: false,
    };
    this.sessions.set(id, session);
    return session;
  }

  get(id: string): ServerSession | undefined {
    return this.sessions.get(id);
  }

  list(): Array<{ id: string; created_at: string; model: string; running: boolean; clients: number }> {
    return [...this.sessions.values()].map((s) => ({
      id: s.id,
      created_at: s.createdAt,
      model: s.config.model,
      running: s.running,
      clients: s.clients.size,
    }));
  }

  /** Drop the session from memory (files stay on disk). Pending approvals are denied. */
  delete(id: string): boolean {
    const s = this.sessions.get(id);
    if (!s) return false;
    for (const [, resolve] of s.approvals) resolve(false);
    s.approvals.clear();
    for (const res of s.clients) {
      try {
        sendSse(res, { type: 'error', message: 'session closed' });
        res.end();
      } catch { /* ignore */ }
    }
    s.clients.clear();
    return this.sessions.delete(id);
  }

  subscribe(s: ServerSession, res: ServerResponse): void {
    s.clients.add(res);
    res.on('close', () => s.clients.delete(res));
  }

  /** Queue a user message; the returned promise settles when the turn completes. */
  send(id: string, text: string): Promise<void> {
    const s = this.sessions.get(id);
    if (!s) throw new Error('unknown session');
    s.queue = s.queue.then(() => this.runTurn(s, text)).catch((err) => {
      this.broadcast(s, { type: 'error', message: (err as Error).message });
    });
    return s.queue;
  }

  /** Resolve a pending approval. Returns false when the call id is unknown. */
  decide(id: string, callId: string, approved: boolean): boolean {
    const s = this.sessions.get(id);
    if (!s) return false;
    const resolve = s.approvals.get(callId);
    if (!resolve) return false;
    s.approvals.delete(callId);
    this.broadcast(s, { type: 'approval_resolved', call_id: callId, approved });
    resolve(approved);
    return true;
  }

  private broadcast(s: ServerSession, event: ServerEvent): void {
    for (const res of s.clients) {
      try {
        sendSse(res, event);
      } catch { /* dead client; 'close' handler removes it */ }
    }
  }

  private async runTurn(s: ServerSession, text: string): Promise<void> {
    s.running = true;
    try {
      s.transcript.push({ role: 'user', content: text });
      appendJsonl(s.jsonlPath, { role: 'user', content: text });

      const onEvent = (e: AgentEvent) => this.broadcast(s, agentEventToServer(e));

      let run: RunResult;
      try {
        run = await runAgent(s.config, text, s.state, { onEvent, jsonlPath: s.jsonlPath });
      } catch (err) {
        this.broadcast(s, { type: 'error', message: (err as Error).message });
        return;
      }

      if (run.status === 'awaiting_hitl' && run.pendingCalls.length > 0) {
        const decider: Decider = (req) =>
          new Promise<boolean>((resolve) => {
            s.approvals.set(req.id, resolve);
            this.broadcast(s, {
              type: 'approval_required',
              call_id: req.id,
              tool: req.name,
              args: req.args,
              heading: req.heading,
              detail: req.detail,
              reason: 'human approval required — original arguments shown unchanged',
            });
            setTimeout(() => {
              if (s.approvals.delete(req.id)) {
                this.broadcast(s, {
                  type: 'approval_resolved',
                  call_id: req.id,
                  approved: false,
                  auto: true,
                });
                resolve(false);
              }
            }, APPROVAL_TIMEOUT_MS);
          });
        try {
          run = await resumeLoop(s.config, run.pendingCalls, s.state, decider, {
            onEvent,
            jsonlPath: s.jsonlPath,
          });
        } catch (err) {
          this.broadcast(s, { type: 'error', message: (err as Error).message });
          return;
        }
      } else if (run.status !== 'complete') {
        this.broadcast(s, { type: 'error', message: `run stopped: ${run.status}` });
        return;
      }

      if (run.text) s.transcript.push({ role: 'assistant', content: run.text });
      s.totals.inputTokens += run.usage.inputTokens;
      s.totals.outputTokens += run.usage.outputTokens;
      s.totals.cost += run.usage.cost;
      this.broadcast(s, {
        type: 'done',
        status: run.status,
        input_tokens: run.usage.inputTokens,
        output_tokens: run.usage.outputTokens,
        cost_usd: run.usage.cost,
        model: s.config.model,
        routed_model: run.routedModel,
      });
    } finally {
      s.running = false;
    }
  }
}
