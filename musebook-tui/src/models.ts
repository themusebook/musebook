export interface ModelInfo {
  id: string;
  name?: string;
  pricing?: Record<string, string>;
}

/** Fetch the OpenRouter model catalog (used by /model and the HTTP server). */
export async function fetchModels(apiKey: string): Promise<ModelInfo[]> {
  const res = await fetch('https://openrouter.ai/api/v1/models', {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as { data: ModelInfo[] };
  return body.data;
}

/** Human price per 1M tokens, e.g. "$2.50" or "free". */
export function per1M(perToken?: string): string {
  if (!perToken) return '—';
  const v = Number(perToken) * 1_000_000;
  return v === 0 ? 'free' : `$${v.toFixed(2)}`;
}
