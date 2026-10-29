#!/usr/bin/env node
// muse-facilitator — run your own x402 facilitator (x402m meta protocol).
//   npx muse-facilitator-kit init --chain solana|evm|both --network mainnet|devnet [--id myfac] [--operator me]
//   npx muse-facilitator-kit serve --port 8787 [--config facilitator.config.json]
import { writeFileSync, existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const args = process.argv.slice(2);
const cmd = args[0];

function flag(name, def = null) {
  const i = args.indexOf(name);
  if (i === -1) return def;
  const v = args[i + 1];
  return v && !v.startsWith("--") ? v : true;
}

function usage() {
  console.log(`muse-facilitator-kit v0 — run your own x402 facilitator

Usage:
  muse-facilitator init --chain solana|evm|both --network mainnet|devnet [--id ID] [--operator NAME]
  muse-facilitator serve [--port 8787] [--config facilitator.config.json]

init scaffolds facilitator.config.json + .env.example in the current directory.
serve starts the facilitator HTTP server (non-custodial: payers sign, you relay).`);
}

const ALL_NETWORKS = {
  solana: {
    mainnet: ["solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"],
    devnet: ["solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"],
  },
  evm: {
    mainnet: ["eip155:8453"],
    devnet: ["eip155:84532"],
  },
};

if (cmd === "init") {
  const chain = flag("--chain", "solana");
  const network = flag("--network", "mainnet");
  const id = flag("--id", "my-facilitator");
  const operator = flag("--operator", "muse-agent");
  if (!["solana", "evm", "both"].includes(chain)) { console.error("--chain must be solana|evm|both"); process.exit(1); }
  if (!["mainnet", "devnet"].includes(network)) { console.error("--network must be mainnet|devnet"); process.exit(1); }
  const chains = chain === "both" ? ["solana", "evm"] : [chain];
  const networks = chains.flatMap((c) => ALL_NETWORKS[c][network]);
  const cfg = {
    id,
    operator,
    networks,
    port: 8787,
    baseUrl: `http://localhost:8787`,
    x402m: "v0",
  };
  const cfgPath = resolve("facilitator.config.json");
  if (existsSync(cfgPath)) { console.error("facilitator.config.json already exists — refusing to overwrite"); process.exit(1); }
  writeFileSync(cfgPath, JSON.stringify(cfg, null, 2) + "\n");
  const envExample = `# Copy to .env and fill in. NEVER commit a real .env.
# Custom RPCs (optional — defaults are public endpoints)
#SOLANA_RPC_URL=https://your-solana-rpc
#SOLANA_DEVNET_RPC_URL=https://your-devnet-rpc
#BASE_RPC_URL=https://your-base-rpc
#BASE_SEPOLIA_RPC_URL=https://your-base-sepolia-rpc
# EVM relay key (OPTIONAL). Only needed to SETTLE EVM authorizations.
# Without it, EVM verify works but settle returns 503 evm_relay_not_configured.
# This key only ever submits other parties' SIGNED EIP-3009 authorizations
# and pays gas — it never moves its own funds. Use a dedicated hot wallet.
#FACILITATOR_EVM_KEY=
# Public base URL of this facilitator (used in the .well-known descriptor)
#FACILITATOR_BASE_URL=https://facilitator.example.com
`;
  if (!existsSync(resolve(".env.example"))) writeFileSync(resolve(".env.example"), envExample);
  console.log(`initialized ${id} (${chain}/${network})`);
  console.log(`  networks: ${networks.join(", ")}`);
  console.log("  files: facilitator.config.json, .env.example");
  console.log("next: cp .env.example .env   # then: muse-facilitator serve --port 8787");
} else if (cmd === "serve") {
  const port = parseInt(flag("--port", process.env.PORT || "8787"), 10);
  const cfgPath = resolve(flag("--config", "facilitator.config.json"));
  if (!existsSync(cfgPath)) {
    console.error(`config not found: ${cfgPath}\nrun: muse-facilitator init --chain solana --network mainnet`);
    process.exit(1);
  }
  // load .env if present (no dependency)
  try {
    const envPath = resolve(".env");
    if (existsSync(envPath)) {
      for (const line of readFileSync(envPath, "utf8").split("\n")) {
        const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/);
        if (m && !(m[1] in process.env)) process.env[m[1]] = m[2];
      }
    }
  } catch { /* optional */ }
  const cfg = JSON.parse(readFileSync(cfgPath, "utf8"));
  const cfgPort = cfg.port;
  cfg.port = port;
  if (process.env.FACILITATOR_BASE_URL) cfg.baseUrl = process.env.FACILITATOR_BASE_URL;
  else if (port !== cfgPort) cfg.baseUrl = `http://localhost:${port}`;
  const { createApp } = await import("../lib/server.js");
  const app = createApp(cfg);
  app.listen(port, () => {
    console.log(`🦞 muse-facilitator "${cfg.id}" listening on :${port}`);
    console.log(`   descriptor: http://localhost:${port}/.well-known/x402-facilitator`);
    console.log(`   networks:   ${cfg.networks.join(", ")}`);
    if (cfg.networks.some((n) => n.startsWith("eip155:"))) {
      const hasKey = /^[0-9a-fA-F]{64}$/.test(String(process.env.FACILITATOR_EVM_KEY || "").replace(/^0x/, ""));
      console.log(`   EVM relay:  ${hasKey ? "ENABLED (key configured)" : "verify-only (set FACILITATOR_EVM_KEY to enable settlement)"}`);
    }
  });
} else {
  usage();
  process.exit(cmd ? 1 : 0);
}
