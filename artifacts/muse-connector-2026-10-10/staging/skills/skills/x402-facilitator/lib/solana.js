// Solana batch settlement: plan (build unsigned tx), verify (check signed tx),
// settle (broadcast + confirm). One payer, one signature, up to 8
// TransferChecked payments in a single transaction (x402m-batch-v0).
import {
  Connection,
  PublicKey,
  TransactionMessage,
  VersionedTransaction,
} from "@solana/web3.js";
import {
  ASSOCIATED_TOKEN_PROGRAM_ID,
  TOKEN_PROGRAM_ID,
  createTransferCheckedInstruction,
  getAssociatedTokenAddress,
} from "@solana/spl-token";
import nacl from "tweetnacl";
import { createHash } from "node:crypto";
import { BATCH_MAX_ITEMS, PLAN_TTL_MS } from "./config.js";

const TRANSFER_CHECKED_IX = 12; // SPL Token program: TransferChecked

export function connectionFor(net) {
  const url = process.env[net.rpcEnv] || net.rpc;
  return new Connection(url, "confirmed");
}

function planIdFor(unsignedTxB64) {
  return "x402m:plan:" + createHash("sha256").update(unsignedTxB64).digest("hex").slice(0, 16);
}

/**
 * Build an UNSIGNED batch transaction template.
 * v0 assumptions (documented, not hidden):
 *  - every recipient already has an associated token account for the asset;
 *    the plan does NOT create ATAs (payer funds creation out of band).
 *  - single asset: the network's USDC mint. Anything else is rejected.
 */
export async function buildBatchPlan(net, { payer, payments, ref }) {
  if (!Array.isArray(payments) || payments.length < 1 || payments.length > BATCH_MAX_ITEMS)
    throw Object.assign(new Error("payments must be 1-8 items"), { status: 400 });
  const payerPk = new PublicKey(payer);
  const mintPk = new PublicKey(net.usdc);
  let total = 0n;
  const items = [];
  for (const p of payments) {
    const amount = BigInt(p.amount ?? "0");
    if (amount <= 0n) throw Object.assign(new Error("amount must be > 0"), { status: 400 });
    if (p.asset && p.asset !== net.usdc)
      throw Object.assign(new Error("batch v0: single asset (USDC) only"), { status: 400 });
    const payToPk = new PublicKey(p.payTo);
    const sourceAta = await getAssociatedTokenAddress(mintPk, payerPk);
    const destAta = await getAssociatedTokenAddress(mintPk, payToPk);
    items.push({ payTo: payToPk.toBase58(), asset: net.usdc, amount: amount.toString(), sourceAta: sourceAta.toBase58(), destAta: destAta.toBase58() });
    total += amount;
  }
  const conn = connectionFor(net);
  const { blockhash } = await conn.getLatestBlockhash("confirmed");
  const ixs = items.map((it) =>
    createTransferCheckedInstruction(
      new PublicKey(it.sourceAta),
      mintPk,
      new PublicKey(it.destAta),
      payerPk,
      BigInt(it.amount),
      net.decimals
    )
  );
  const msg = new TransactionMessage({
    payerKey: payerPk,
    recentBlockhash: blockhash,
    instructions: ixs,
  }).compileToV0Message();
  const tx = new VersionedTransaction(msg); // zero signatures
  const unsignedTx = Buffer.from(tx.serialize()).toString("base64");
  return {
    ok: true,
    planId: planIdFor(unsignedTx),
    unsignedTx,
    blockhash,
    expiresAt: Date.now() + PLAN_TTL_MS,
    items: items.map(({ payTo, asset, amount }) => ({ payTo, asset, amount })),
    totalAmount: total.toString(),
    instructionCount: ixs.length,
    ref: ref || null,
  };
}

function decodeTransferChecked(ix, i) {
  if (!ix.programId.equals(TOKEN_PROGRAM_ID))
    throw new Error(`invalid_batch: instruction ${i} is not the token program`);
  const d = ix.data;
  if (d.length < 10 || d[0] !== TRANSFER_CHECKED_IX)
    throw new Error(`invalid_batch: instruction ${i} is not TransferChecked`);
  const amount = d.readBigUInt64LE(1); // bytes 1..8
  const decimals = d[9]; // byte 9
  return { amount, decimals };
}

/**
 * Verify a SIGNED batch transaction against its plan.
 * Strict allowlist: ONLY TransferChecked for the exact asset, payer as the
 * sole authority, every planned payment present with amount >= required.
 */
export function verifyBatchTx(net, paymentHeaderB64, plan) {
  const bytes = Buffer.from(String(paymentHeaderB64 || ""), "base64");
  let tx;
  try {
    tx = VersionedTransaction.deserialize(bytes);
  } catch {
    throw Object.assign(new Error("invalid_exact_svm_payload"), { status: 400 });
  }
  const msg = tx.message;
  const payer = new PublicKey(msg.staticAccountKeys[0]);
  if (plan?.payer && payer.toBase58() !== plan.payer)
    throw Object.assign(new Error("payer_mismatch"), { status: 400 });
  // every required signature present and valid
  const msgBytes = msg.serialize();
  const signers = msg.header.numRequiredSignatures;
  for (let s = 0; s < signers; s++) {
    const sig = tx.signatures[s];
    if (!sig || sig.every((b) => b === 0))
      throw Object.assign(new Error("missing_signature"), { status: 400 });
    const ok = nacl.sign.detached.verify(msgBytes, sig, msg.staticAccountKeys[s].toBytes());
    if (!ok) throw Object.assign(new Error("invalid_signature"), { status: 400 });
  }
  const mintPk = new PublicKey(net.usdc);
  const expected = plan?.items || [];
  const seen = new Map(); // destAta -> amount
  for (let i = 0; i < msg.compiledInstructions.length; i++) {
    const ci = msg.compiledInstructions[i];
    const programId = msg.staticAccountKeys[ci.programIdIndex];
    // resolve account metas in order
    const keys = ci.accountKeyIndexes.map((k) => msg.staticAccountKeys[k]);
    const { amount, decimals } = decodeTransferChecked({ programId, data: Buffer.from(ci.data) }, i);
    if (decimals !== net.decimals) throw new Error(`invalid_batch: instruction ${i} wrong decimals`);
    // TransferChecked layout: [source, mint, destination, authority, ...]
    if (keys.length < 4) throw new Error(`invalid_batch: instruction ${i} malformed accounts`);
    if (!keys[1].equals(mintPk)) throw new Error(`invalid_batch: instruction ${i} wrong mint`);
    if (!keys[3].equals(payer)) throw new Error(`invalid_batch: instruction ${i} authority is not the payer`);
    if (keys[0].equals(payer) || programId.equals(payer))
      throw new Error("invalid_batch: facilitator/payer account confusion");
    seen.set(keys[2].toBase58(), (seen.get(keys[2].toBase58()) || 0n) + amount);
  }
  const items = [];
  let total = 0n;
  for (const e of expected) {
    const destAta = deriveAta(e.payTo, mintPk).toBase58();
    const got = seen.get(destAta) || 0n;
    if (got < BigInt(e.amount))
      throw Object.assign(new Error("insufficient_amount"), { status: 400 });
    items.push({ payTo: e.payTo, asset: e.asset, amount: got.toString() });
    total += got;
  }
  // no extra unexpected transfers
  if (seen.size !== expected.length)
    throw Object.assign(new Error("invalid_batch: unexpected extra transfers"), { status: 400 });
  return { isValid: true, payer: payer.toBase58(), items, totalAmount: total.toString() };
}

// Sync ATA derivation (same PDA as getAssociatedTokenAddress; verify is sync
// so we recompute the deterministic address here instead of the async helper)
function deriveAta(payTo, mintPk) {
  const [addr] = PublicKey.findProgramAddressSync(
    [new PublicKey(payTo).toBytes(), TOKEN_PROGRAM_ID.toBytes(), mintPk.toBytes()],
    ASSOCIATED_TOKEN_PROGRAM_ID
  );
  return addr;
}

export async function settleBatchTx(net, paymentHeaderB64) {
  const conn = connectionFor(net);
  const raw = Buffer.from(String(paymentHeaderB64 || ""), "base64");
  const sig = await conn.sendRawTransaction(raw, { skipPreflight: false, preflightCommitment: "confirmed" });
  const st = await conn.confirmTransaction(sig, "confirmed").catch(() => null);
  return { signature: sig, confirmed: !!(st && !st.value?.err) };
}
