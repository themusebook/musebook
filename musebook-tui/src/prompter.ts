import { createInterface, type Interface } from 'node:readline';

// Single owner of stdin for the whole TUI. One 'line' listener feeds both the
// main REPL and the HITL approval prompts, so answers never get swallowed by
// competing readers. Works on TTY and piped stdin alike.
export interface Prompter {
  rl: Interface;
  ask: (prefix?: string) => Promise<string>;
  close: () => void;
}

export function createPrompter(): Prompter {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const queued: string[] = [];
  let waiting: ((line: string) => void) | null = null;

  rl.on('line', (line) => {
    if (waiting) {
      const resolve = waiting;
      waiting = null;
      resolve(line);
    } else {
      queued.push(line);
    }
  });

  const ask = (prefix?: string): Promise<string> =>
    new Promise((resolve) => {
      if (queued.length > 0) {
        resolve(queued.shift()!);
        return;
      }
      if (prefix) process.stdout.write(prefix);
      waiting = resolve;
    });

  return { rl, ask, close: () => rl.close() };
}
