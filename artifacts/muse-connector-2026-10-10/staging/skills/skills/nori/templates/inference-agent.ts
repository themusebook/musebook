/**
 * inference-agent.ts — Nori chat.completion with tool calls.
 *
 * OpenAI-compatible client pointed at {NORI_URL}/v1. Models are addressed as
 * <provider>/<model>, e.g. "anthropic/claude-sonnet-4-6", "openai/gpt-5.4",
 * "google/gemini-2.5-flash". Non-streaming.
 *
 * Billing: charge-on-success. First call may return 402 (x402) or require a
 * delegate-pay bearer from POST {NORI_URL}/auth/handshake — get the user's
 * explicit approval of the exact spend before paying anything.
 *
 * Run:  NORI_URL=https://nori.example.com npx tsx templates/inference-agent.ts
 *       (or compile with tsc; needs node 18+ for global fetch)
 */

const NORI_URL = (process.env.NORI_URL ?? "").replace(/\/$/, "");
if (!NORI_URL) {
  console.error("Set NORI_URL first, e.g. export NORI_URL=https://nori.example.com");
  process.exit(1);
}
// Optional: bearer from a user-approved delegate-pay handshake, or an x402
// payment proof. Never hardcode secrets here.
const AUTH: Record<string, string> = process.env.NORI_BEARER ? { Authorization: `Bearer ${process.env.NORI_BEARER}` } : {};

type ToolDef = { type: "function"; function: { name: string; description: string; parameters: object } };

const tools: ToolDef[] = [
  {
    type: "function",
    function: {
      name: "get_sol_price",
      description: "Return a mock SOL price in USD (example local tool).",
      parameters: { type: "object", properties: {}, additionalProperties: false },
    },
  },
];

// Local implementations of the tools declared above.
const toolImpls: Record<string, () => unknown> = {
  get_sol_price: () => ({ sol_usd: 123.45, source: "example-stub" }),
};

async function chat(messages: any[]): Promise<any> {
  const res = await fetch(`${NORI_URL}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...AUTH },
    body: JSON.stringify({
      model: "openai/gpt-5.4", // or "anthropic/claude-sonnet-4-6", "google/gemini-2.5-flash", ...
      messages,
      tools,
      tool_choice: "auto",
    }),
  });
  if (res.status === 402) {
    throw new Error("402 payment required — check the rate card and get user approval before paying.");
  }
  if (!res.ok) throw new Error(`chat.completion failed: ${res.status} ${await res.text()}`);
  return res.json();
}

async function main() {
  const messages = [{ role: "user", content: "What is the SOL price right now? Use the tool." }];
  for (let i = 0; i < 5; i++) {
    const data = await chat(messages);
    const msg = data.choices[0].message;
    messages.push(msg);
    if (!msg.tool_calls?.length) {
      console.log("assistant:", msg.content);
      return;
    }
    for (const tc of msg.tool_calls) {
      const fn = toolImpls[tc.function.name];
      const result = fn ? fn() : { error: `unknown tool ${tc.function.name}` };
      console.log(`tool ${tc.function.name} ->`, JSON.stringify(result));
      messages.push({ role: "tool", tool_call_id: tc.id, content: JSON.stringify(result) });
    }
  }
  console.log("stopped after 5 tool rounds");
}

main().catch((e) => { console.error(e.message); process.exit(1); });
