/**
 * artwork-agent.ts — Nori image.generation.
 *
 * POST {NORI_URL}/v1/images/generations, model "openai/gpt-image-1".
 * Flat per-image price — check GET {NORI_URL}/rate-card first.
 *
 * Billing: charge-on-success (delegate-pay bearer or x402). Get the user's
 * explicit approval of the exact spend before generating.
 *
 * Run:  NORI_URL=https://nori.example.com npx tsx templates/artwork-agent.ts "a lobster in cyberspace"
 */

const NORI_URL = (process.env.NORI_URL ?? "").replace(/\/$/, "");
if (!NORI_URL) {
  console.error("Set NORI_URL first, e.g. export NORI_URL=https://nori.example.com");
  process.exit(1);
}
const AUTH: Record<string, string> = process.env.NORI_BEARER ? { Authorization: `Bearer ${process.env.NORI_BEARER}` } : {};

const prompt = process.argv[2] ?? "a lobster astronaut, neon solana colors, digital art";

async function main() {
  const res = await fetch(`${NORI_URL}/v1/images/generations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...AUTH },
    body: JSON.stringify({
      model: "openai/gpt-image-1",
      prompt,
      size: "1024x1024",
    }),
  });
  if (res.status === 402) {
    throw new Error("402 payment required — check the rate card and get user approval before paying.");
  }
  if (!res.ok) throw new Error(`image.generation failed: ${res.status} ${await res.text()}`);
  const data = await res.json();
  // OpenAI-compatible shape: data.data[0].url or .b64_json
  const first = data.data?.[0];
  if (!first) {
    console.log(JSON.stringify(data, null, 2).slice(0, 2000));
    return;
  }
  if (first.url) console.log("image url:", first.url);
  if (first.b64_json) {
    const fs = await import("node:fs");
    fs.writeFileSync("nori-artwork.png", Buffer.from(first.b64_json, "base64"));
    console.log("saved nori-artwork.png");
  }
}

main().catch((e) => { console.error(e.message); process.exit(1); });
