import { z } from 'zod';

// Jev — probability judgments over tool calls, via OpenRouter's Decisions API.
// One request costs a fraction of a cent and returns a probability per question.
const JEV_MODEL = 'typesafe/jev-1.13';
const DECISIONS_URL = 'https://openrouter.ai/api/alpha/decisions';

export const APPROVE_AT = 0.9;
export const BLOCK_AT = 0.1;

export type NoulQuestion = { type: 'noul'; instructions: string };

const JevResponse = z.object({
  model: z.string(),
  answers: z.record(
    z.string(),
    z.object({ type: z.literal('noul'), noul: z.number().min(0).max(1) }),
  ),
  usage: z
    .object({
      input_tokens: z.number(),
      output_tokens: z.number(),
      cost: z.number().optional(),
    })
    .optional(),
});

export async function askJev<K extends string>(
  state: unknown,
  questions: Record<K, NoulQuestion>,
): Promise<Record<K, number>> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) throw new Error('OPENROUTER_API_KEY is required for Jev gating');
  const res = await fetch(DECISIONS_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ model: JEV_MODEL, state, questions }),
  });
  if (!res.ok) throw new Error(`Decisions ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const { answers } = JevResponse.parse(await res.json());
  const keys = Object.keys(questions) as K[];
  const missing = keys.filter((k) => answers[k] === undefined);
  if (missing.length > 0) throw new Error(`Jev did not answer: ${missing.join(', ')}`);
  return Object.fromEntries(keys.map((k) => [k, answers[k]!.noul])) as Record<K, number>;
}

export type GateDecision = {
  outcome: 'approve' | 'block' | 'review';
  reason: string;
  checks: Record<string, number> | null;
};

/**
 * Deterministic precheck first (no inference spent), then Jev.
 * approve: every check >= 0.9. block: any check <= 0.1. else: review (human).
 * A Jev failure never approves — it becomes a review so the human decides.
 */
export async function gateAction<K extends string>(
  actionLabel: string,
  precheck: () => string | null,
  state: unknown,
  questions: Record<K, NoulQuestion>,
): Promise<GateDecision> {
  const problem = precheck();
  if (problem !== null) return { outcome: 'block', reason: problem, checks: null };
  let checks: Record<string, number>;
  try {
    checks = await askJev(state, questions);
  } catch (err) {
    return {
      outcome: 'review',
      reason: `Jev unavailable (${(err as Error).message}) — human decides`,
      checks: null,
    };
  }
  const values = Object.values(checks);
  if (values.every((p) => p >= APPROVE_AT)) {
    return { outcome: 'approve', reason: 'every check clear', checks };
  }
  const failed = Object.entries(checks)
    .filter(([, p]) => p <= BLOCK_AT)
    .map(([name, p]) => `${name}=${p.toFixed(2)}`);
  if (failed.length > 0) {
    return { outcome: 'block', reason: `failed ${failed.join(', ')}`, checks };
  }
  return { outcome: 'review', reason: 'no check clearly true or false', checks };
}

export function formatGate(d: GateDecision): string {
  const checks = d.checks
    ? ' ' + Object.entries(d.checks).map(([k, v]) => `${k}=${v.toFixed(2)}`).join(' ')
    : '';
  return `${d.outcome.toUpperCase()} — ${d.reason}${checks}`;
}
