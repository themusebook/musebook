/**
 * portfolio-analyzer.ts — Nori solana.rpc pass-through.
 *
 * POST {NORI_URL}/v1/solana/rpc with a standard JSON-RPC envelope.
 * Transparent pass-through INCLUDING DAS methods: getAsset, getAssetsByOwner.
 * Flat per-call price — check GET {NORI_URL}/rate-card first.
 *
 * Read-only. Billing: charge-on-success (delegate-pay bearer or x402).
 *
 * Run:  NORI_URL=https://nori.example.com npx tsx templates/portfolio-analyzer.ts <wallet-address>
 */

const NORI_URL = (process.env.NORI_URL ?? "").replace(/\/$/, "");
if (!NORI_URL) {
  console.error("Set NORI_URL first, e.g. export NORI_URL=https://nori.example.com");
  process.exit(1);
}
const AUTH: Record<string, string> = process.env.NORI_BEARER ? { Authorization: `Bearer ${process.env.NORI_BEARER}` } : {};

const wallet = process.argv[2];
if (!wallet) {
  console.error("usage: portfolio-analyzer.ts <wallet-address>");
  process.exit(1);
}

async function rpc(method: string, params: unknown[]) {
  const res = await fetch(`${NORI_URL}/v1/solana/rpc`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...AUTH },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  if (res.status === 402) {
    throw new Error("402 payment required — check the rate card and get user approval before paying.");
  }
  if (!res.ok) throw new Error(`solana.rpc failed: ${res.status} ${await res.text()}`);
  const data = await res.json();
  if (data.error) throw new Error(`rpc error: ${JSON.stringify(data.error)}`);
  return data.result;
}

async function main() {
  // 1. Native SOL balance (lamports)
  const balance = await rpc("getBalance", [wallet]);
  console.log(`SOL balance: ${(balance.value / 1e9).toFixed(4)} SOL`);

  // 2. DAS: all assets owned by the wallet (compressed + core + SPL)
  const assets = await rpc("getAssetsByOwner", [
    wallet,
    { sortBy: { sortBy: "created", sortDirection: "desc" }, limit: 25, page: 1, displayOptions: { showFungible: true } },
  ]);
  const items = assets.items ?? [];
  console.log(`assets: ${assets.total ?? items.length} total, showing ${items.length}`);
  for (const a of items.slice(0, 10)) {
    const name = a.content?.metadata?.name ?? a.id.slice(0, 8);
    const kind = a.interface ?? a.content?.metadata?.token_standard ?? "unknown";
    console.log(`  - ${name} (${kind}) ${a.id}`);
  }
}

main().catch((e) => { console.error(e.message); process.exit(1); });
