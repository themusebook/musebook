// EVM exact settlement (x402): EIP-712 signature over an EIP-3009
// TransferWithAuthorization. The facilitator recovers the signer, enforces
// asset/recipient/amount/validity, checks the nonce is unused on-chain
// (authorizationState), then relays via transferWithAuthorization using
// FACILITATOR_EVM_KEY when configured (503 evm_relay_not_configured without it).
//
// The relay key ONLY ever submits other parties' signed authorizations and
// pays gas. It never moves its own funds.
import {
  createPublicClient,
  createWalletClient,
  http,
  recoverTypedDataAddress,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { base, baseSepolia } from "viem/chains";
import { rpcUrl } from "./config.js";

const CHAINS = { 8453: base, 84532: baseSepolia };

const TRANSFER_WITH_AUTH_TYPES = {
  TransferWithAuthorization: [
    { name: "from", type: "address" },
    { name: "to", type: "address" },
    { name: "value", type: "uint256" },
    { name: "validAfter", type: "uint256" },
    { name: "validBefore", type: "uint256" },
    { name: "nonce", type: "bytes32" },
  ],
};

const USDC_ABI = [
  {
    name: "authorizationState",
    type: "function",
    stateMutability: "view",
    inputs: [
      { name: "authorizer", type: "address" },
      { name: "nonce", type: "bytes32" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    name: "transferWithAuthorization",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "from", type: "address" },
      { name: "to", type: "address" },
      { name: "value", type: "uint256" },
      { name: "validAfter", type: "uint256" },
      { name: "validBefore", type: "uint256" },
      { name: "nonce", type: "bytes32" },
      { name: "signature", type: "bytes" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
];

export function publicClientFor(net) {
  return createPublicClient({ chain: CHAINS[net.chainId], transport: http(rpcUrl(net)) });
}

function fail(msg, status = 400) {
  throw Object.assign(new Error(msg), { status });
}

export async function verifyEvmExact(net, paymentPayload, paymentRequirements) {
  const req = paymentRequirements || {};
  const payload = paymentPayload || {};
  const auth = payload.authorization || {};
  const signature = payload.signature;
  if (!signature || !auth.from || !auth.to || auth.value == null || !auth.nonce)
    fail("invalid_exact_evm_payload");
  const asset = String(req.asset || "");
  if (asset.toLowerCase() !== net.usdc.toLowerCase()) fail("invalid_asset");
  if (req.payTo && String(auth.to).toLowerCase() !== String(req.payTo).toLowerCase())
    fail("wrong_recipient");
  const required = BigInt(req.maxAmountRequired ?? "0");
  const value = BigInt(auth.value);
  if (required > 0n && value < required) fail("insufficient_amount");

  const domain = {
    name: net.usdcName,
    version: net.usdcVersion,
    chainId: net.chainId,
    verifyingContract: net.usdc,
  };
  const message = {
    from: auth.from,
    to: auth.to,
    value,
    validAfter: BigInt(auth.validAfter ?? "0"),
    validBefore: BigInt(auth.validBefore),
    nonce: auth.nonce,
  };
  let signer;
  try {
    signer = await recoverTypedDataAddress({
      domain,
      types: TRANSFER_WITH_AUTH_TYPES,
      primaryType: "TransferWithAuthorization",
      message,
      signature,
    });
  } catch {
    fail("invalid_exact_evm_payload_signature");
  }
  if (signer.toLowerCase() !== String(auth.from).toLowerCase())
    fail("invalid_exact_evm_payload_signature");

  const now = Math.floor(Date.now() / 1000);
  if (now < Number(auth.validAfter ?? "0") || now > Number(auth.validBefore))
    fail("authorization_expired");

  // replay check: nonce must be unused on-chain
  const client = publicClientFor(net);
  let used;
  try {
    used = await client.readContract({
      address: net.usdc,
      abi: USDC_ABI,
      functionName: "authorizationState",
      args: [auth.from, auth.nonce],
    });
  } catch {
    fail("rpc_unavailable", 502);
  }
  if (used) fail("authorization_already_used");

  return {
    from: String(auth.from).toLowerCase(),
    to: String(auth.to).toLowerCase(),
    value: value.toString(),
    auth,
    signature,
    domain,
  };
}

export async function settleEvmAuthorization(net, verified) {
  const keyHex = String(process.env.FACILITATOR_EVM_KEY || "").replace(/^0x/, "");
  if (!/^[0-9a-fA-F]{64}$/.test(keyHex)) fail("evm_relay_not_configured", 503);
  const account = privateKeyToAccount(("0x" + keyHex));
  const wallet = createWalletClient({
    chain: CHAINS[net.chainId],
    transport: http(rpcUrl(net)),
    account,
  });
  const publicClient = publicClientFor(net);
  const { auth, signature } = verified;
  const hash = await wallet.writeContract({
    address: net.usdc,
    abi: USDC_ABI,
    functionName: "transferWithAuthorization",
    args: [
      auth.from,
      auth.to,
      BigInt(auth.value),
      BigInt(auth.validAfter ?? "0"),
      BigInt(auth.validBefore),
      auth.nonce,
      signature,
    ],
  });
  const receipt = await publicClient.waitForTransactionReceipt({ hash }).catch(() => null);
  return { hash, confirmed: receipt?.status === "success" };
}
