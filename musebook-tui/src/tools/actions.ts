import { execFile } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { tool } from '@openrouter/agent';
import { z } from 'zod';
import { formatGate, gateAction, type NoulQuestion } from '../jev.js';

const NOTES_DIR = join(homedir(), '.musebook', 'tui', 'notes');

// Only these hosts may be opened from the TUI. Everything else is refused
// by a deterministic check before Jev is even consulted.
const ALLOWED_HOSTS = new Set([
  'musebook.trade',
  'www.musebook.trade',
  'api.musebook.trade',
  'musebook.x402.life',
  'solscan.io',
  'x.com',
  'github.com',
  'openrouter.ai',
]);

function hostOf(url: string): string | null {
  try {
    const u = new URL(url);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    return u.hostname.toLowerCase();
  } catch {
    return null;
  }
}

function openUrl(url: string): void {
  if (process.platform === 'win32') {
    execFile('rundll32.exe', ['url.dll,FileProtocolHandler', url]);
  } else {
    execFile(process.platform === 'darwin' ? 'open' : 'xdg-open', [url]);
  }
}

function slugify(title: string): string {
  return (
    title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'note'
  );
}

function saveNoteFile(title: string, body: string): string {
  mkdirSync(NOTES_DIR, { recursive: true });
  const path = join(NOTES_DIR, `${Date.now()}-${slugify(title)}.md`);
  writeFileSync(path, `# ${title}\n\n${body}\n`, 'utf-8');
  return path;
}

// ---------------------------------------------------------------------------
// open_in_browser — always pauses for human consent (the pause prompt shows
// the deterministic host check result). Nothing opens without a yes.
// ---------------------------------------------------------------------------
export const openInBrowserTool = tool({
  name: 'open_in_browser',
  description:
    'Open a URL in the user\'s browser. Only Musebook/API, Solscan, X, GitHub, and OpenRouter links are allowed. Always asks the human first.',
  inputSchema: z.object({
    url: z.string().describe('https URL to open'),
    reason: z.string().optional().describe('Why this link is useful'),
  }),
  outputSchema: z.object({
    opened: z.boolean(),
    note: z.string().optional(),
  }),
  onToolCalled: async (input) => {
    const host = hostOf(input.url);
    if (!host || !ALLOWED_HOSTS.has(host)) {
      return { opened: false, note: `Refused: ${input.url} is not an allowed host` };
    }
    return null; // pause — the human consents in the TUI
  },
  onResponseReceived: async (raw) => {
    const decision = z.object({ approved: z.boolean() }).parse(raw);
    // Re-validate at execution time: the URL comes from the pending call.
    const pending = (raw as { url?: string }).url;
    if (decision.approved && typeof pending === 'string') {
      const host = hostOf(pending);
      if (host && ALLOWED_HOSTS.has(host)) {
        openUrl(pending);
        return { opened: true };
      }
    }
    return { opened: false, note: 'Declined by user' };
  },
});

// ---------------------------------------------------------------------------
// save_note — Jev-gated: auto-saves when clearly asked for, refuses when the
// content looks wrong, pauses for a human when ambiguous.
// ---------------------------------------------------------------------------
const NOTE_POLICY = [
  'Notes are local markdown drafts in ~/.musebook/tui/notes.',
  'A note must be the user\'s own draft: ideas, reminders, summaries.',
  'Never save API keys, mnemonics, private keys, passwords, or secrets.',
].join('\n');

const noteChecks = {
  user_asked: {
    type: 'noul',
    instructions: 'The user asked to save a note in this conversation.',
  },
  safe_content: {
    type: 'noul',
    instructions:
      'The note title and body contain no API keys, mnemonics, private keys, passwords, or other secrets.',
  },
  policy_ok: {
    type: 'noul',
    instructions:
      'Saving this note as a local markdown draft is consistent with NOTE_POLICY.',
  },
} satisfies Record<string, NoulQuestion>;

export const saveNoteTool = tool({
  name: 'save_note',
  description:
    'Save a markdown note locally (title + body) under ~/.musebook/tui/notes. Auto-saves when the request is clear; otherwise asks the human.',
  inputSchema: z.object({
    title: z.string().describe('Note title'),
    body: z.string().describe('Note body in markdown'),
  }),
  outputSchema: z.object({
    saved: z.boolean(),
    path: z.string().optional(),
    note: z.string().optional(),
  }),
  onToolCalled: async (input) => {
    const decision = await gateAction(
      'save_note',
      () => {
        if (!input.title.trim() || !input.body.trim()) return 'title and body are required';
        return null;
      },
      { policy: NOTE_POLICY, title: input.title, body: input.body },
      noteChecks,
    );
    console.log(`  \x1b[2mjev save_note: ${formatGate(decision)}\x1b[0m`);
    if (decision.outcome === 'approve') {
      const path = saveNoteFile(input.title, input.body);
      return { saved: true, path };
    }
    if (decision.outcome === 'block') {
      return { saved: false, note: `Refused by note gate: ${decision.reason}` };
    }
    return null; // review -> pause for the human
  },
  onResponseReceived: async (raw) => {
    // The SDK only hands onResponseReceived the resume output — never the
    // original call arguments — so the human's approval embeds title/body.
    const review = z
      .object({
        decision: z.enum(['approve', 'deny']),
        note: z.string().optional(),
        title: z.string().optional(),
        body: z.string().optional(),
      })
      .parse(raw);
    if (review.decision === 'deny') {
      return { saved: false, note: review.note ?? 'Denied by user' };
    }
    const title = review.title ?? 'untitled';
    const body = review.body ?? '';
    if (!title.trim() || !body.trim()) return { saved: false, note: 'Missing title/body' };
    const path = saveNoteFile(title, body);
    return { saved: true, path };
  },
});

// ---------------------------------------------------------------------------
// draft_agent_registration — informational: builds the one-shot registration
// checklist for the user's agent idea. Read-only, auto-resolves.
// ---------------------------------------------------------------------------
export const draftAgentRegistrationTool = tool({
  name: 'draft_agent_registration',
  description:
    'Draft a Musebook agent registration plan: the one-shot browser-signed flow steps, what the user needs ready, and links. Does not register anything on-chain.',
  inputSchema: z.object({
    name: z.string().describe('Proposed agent name'),
    description: z.string().optional().describe('What the agent does'),
  }),
  outputSchema: z.object({
    plan: z.string(),
  }),
  execute: async ({ name, description }) => {
    const plan = [
      `# Register "${name}" on Musebook`,
      '',
      description ? `> ${description}` : '',
      '',
      'The one-shot flow is browser-signed and non-custodial — no local keypairs:',
      '',
      '1. Install the skill: `curl -fsSL https://musebook.trade/install.sh | bash`',
      '2. The installer reserves your directory entry and opens the mint wizard.',
      '3. In the wizard: connect your Solana wallet, fund the derived Asset Signer PDA, sign the mint.',
      '4. The wizard completes the registration and your agent appears in the directory.',
      '',
      'Links:',
      '- Directory: https://musebook.trade',
      '- Docs: https://musebook.trade/docs',
      '- API reference: https://api.musebook.trade/reference/',
      '- OpenAPI spec: https://api.musebook.trade/openapi.json',
      '- Remote MCP: https://musebook.trade/mcp',
    ]
      .filter((l) => l !== '')
      .join('\n');
    return { plan };
  },
});

export const actionTools = [openInBrowserTool, saveNoteTool, draftAgentRegistrationTool];
