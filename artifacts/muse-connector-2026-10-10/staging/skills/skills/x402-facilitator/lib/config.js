// Network + asset presets for the x402m facilitator kit.
// CAIP-2 ids are the canonical network keys everywhere in x402m.
export const NETWORKS = {
  "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp": {
    kind: "solana",
    label: "solana",
    rpc: "https://api.mainnet-beta.solana.com",
    rpcEnv: "SOLANA_RPC_URL",
    usdc: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    decimals: 6,
  },
  "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1": {
    kind: "solana",
    label: "solana-devnet",
    rpc: "https://api.devnet.solana.com",
    rpcEnv: "SOLANA_DEVNET_RPC_URL",
    usdc: "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
    decimals: 6,
  },
  "eip155:8453": {
    kind: "evm",
    label: "base",
    chainId: 8453,
    rpc: "https://mainnet.base.org",
    rpcEnv: "BASE_RPC_URL",
    usdc: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    // EIP-712 domain fields for this USDC deployment
    usdcName: "USD Coin",
    usdcVersion: "2",
    decimals: 6,
  },
  "eip155:84532": {
    kind: "evm",
    label: "base-sepolia",
    chainId: 84532,
    rpc: "https://sepolia.base.org",
    rpcEnv: "BASE_SEPOLIA_RPC_URL",
    usdc: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    usdcName: "USDC",
    usdcVersion: "2",
    decimals: 6,
  },
};

export const EVM_ALIASES = { base: "eip155:8453", "base-sepolia": "eip155:84532" };

export function resolveNetwork(name) {
  if (NETWORKS[name]) return { caip: name, net: NETWORKS[name] };
  const caip = EVM_ALIASES[String(name || "").toLowerCase()];
  if (caip && NETWORKS[caip]) return { caip, net: NETWORKS[caip] };
  return null;
}

export function rpcUrl(net) {
  return process.env[net.rpcEnv] || net.rpc;
}

export const BATCH_MAX_ITEMS = 8;
export const PLAN_TTL_MS = 5 * 60 * 1000;
