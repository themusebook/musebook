import { appendFileSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import type { ConversationState, StateAccessor } from '@openrouter/agent';

export interface SessionMeta {
  id: string;
  model: string;
  startedAt: string;
}

export function newSessionDir(sessionDir: string): string {
  mkdirSync(sessionDir, { recursive: true });
  return sessionDir;
}

/** New session: a JSONL transcript path + a state file path. */
export function newSession(sessionDir: string): { jsonlPath: string; statePath: string; meta: SessionMeta } {
  newSessionDir(sessionDir);
  const id = new Date().toISOString().replace(/[:.]/g, '-');
  const meta: SessionMeta = {
    id,
    model: '',
    startedAt: new Date().toISOString(),
  };
  return {
    jsonlPath: `${sessionDir}/${id}.jsonl`,
    statePath: `${sessionDir}/${id}.state.json`,
    meta,
  };
}

export function appendJsonl(path: string, obj: Record<string, unknown>): void {
  try {
    appendFileSync(path, JSON.stringify(obj) + '\n', 'utf-8');
  } catch {
    // transcript is best-effort; never break the run
  }
}

/**
 * File-backed StateAccessor with atomic writes (tmp + rename), so a crash
 * mid-write cannot corrupt the session. Only ENOENT is swallowed on load —
 * real I/O errors surface instead of silently restarting from scratch.
 */
export function fileStateAccessor(statePath: string): StateAccessor {
  return {
    load: async () => {
      let raw: string;
      try {
        raw = readFileSync(statePath, 'utf-8');
      } catch (err: unknown) {
        if ((err as NodeJS.ErrnoException).code === 'ENOENT') return null;
        throw err;
      }
      return JSON.parse(raw) as ConversationState;
    },
    save: async (state) => {
      const tmp = `${statePath}.tmp`;
      writeFileSync(tmp, JSON.stringify(state));
      renameSync(tmp, statePath);
    },
  };
}

/** Read back a JSONL transcript as markdown-ish text (for /export). */
export function readTranscript(jsonlPath: string): Array<{ role: string; content: string }> {
  try {
    return readFileSync(jsonlPath, 'utf-8')
      .split('\n')
      .filter(Boolean)
      .map((line) => JSON.parse(line) as { role: string; content: string });
  } catch {
    return [];
  }
}
