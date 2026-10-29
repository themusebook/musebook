/**
 * a2a-caller.ts — Nori A2A interface.
 *
 * POST {NORI_URL}/a2a with a JSON-RPC 2.0 envelope: method "message/send",
 * params.message.parts[] containing a DataPart with { skill, input }.
 * (message/sendStream is not implemented — returns 501.)
 *
 * Billing: charge-on-success (delegate-pay bearer or x402). Get the user's
 * explicit approval of the exact spend before sending.
 *
 * Run:  NORI_URL=https://nori.example.com npx tsx templates/a2a-caller.ts infer "Summarize this wallet: ..."
 */

const NORI_URL = (process.env.NORI_URL ?? "").replace(/\/$/, "");
if (!NORI_URL) {
  console.error("Set NORI_URL first, e.g. export NORI_URL=https://nori.example.com");
  process.exit(1);
}
const AUTH: Record<string, string> = process.env.NORI_BEARER ? { Authorization: `Bearer ${process.env.NORI_BEARER}` } : {};

const skill = process.argv[2] ?? "infer";
const input = process.argv[3] ?? "Hello from an A2A caller.";

async function main() {
  const envelope = {
    jsonrpc: "2.0",
    id: `a2a-${Date.now()}`,
    method: "message/send",
    params: {
      message: {
        role: "user",
        parts: [
          {
            kind: "data", // DataPart
            data: { skill, input },
          },
        ],
      },
    },
  };

  const res = await fetch(`${NORI_URL}/a2a`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...AUTH },
    body: JSON.stringify(envelope),
  });
  if (res.status === 402) {
    throw new Error("402 payment required — check the rate card and get user approval before paying.");
  }
  if (res.status === 501) {
    throw new Error("501 — this A2A method is not implemented (use message/send, not message/sendStream).");
  }
  if (!res.ok) throw new Error(`a2a failed: ${res.status} ${await res.text()}`);
  const data = await res.json();
  console.log(JSON.stringify(data, null, 2).slice(0, 4000));
}

main().catch((e) => { console.error(e.message); process.exit(1); });
