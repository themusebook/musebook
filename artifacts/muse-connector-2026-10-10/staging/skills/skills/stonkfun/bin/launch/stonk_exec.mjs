// Stonkfun LaunchLab launch executor (Node side).
// Reads a JSON bundle on stdin:
//   { plan, creatorSecret: [...64], mintSecret: [...64] | null,
//     mode: "dry-run" | "execute", rpc: "https://..." }
// Builds initialize_with_token2022 from the plan, signs with creator + mint
// keypair, and (execute only) simulates then broadcasts.
//
// Safety: refuses any plan whose program id is not the pinned LaunchLab
// program; builds exactly ONE program instruction (+ compute budget).
// Secrets live only in this process's memory, never printed.
import {
  ComputeBudgetProgram, Connection, Keypair, PublicKey, Transaction,
} from '@solana/web3.js';
import {
  getPdaLaunchpadAuth, getPdaLaunchpadPoolId, getPdaLaunchpadVaultId,
  initializeWithToken2022, CpmmCreatorFeeOn,
} from '@raydium-io/raydium-sdk-v2';
import BN from 'bn.js';

const EXPECTED_PROGRAM_ID = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj';
const TOKEN_2022_PROGRAM_ID = 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb';

const fail = (msg) => { console.log(JSON.stringify({ ok: false, error: msg })); process.exit(1); };

async function main() {
  let input;
  try {
    input = JSON.parse(await new Promise((res, rej) => {
      let s = '';
      process.stdin.on('data', (d) => { s += d; });
      process.stdin.on('end', () => res(s));
      process.stdin.on('error', rej);
    }));
  } catch (e) { fail('bad stdin JSON: ' + e.message); }

  const { plan, creatorSecret, mintSecret, mode, rpc } = input;
  if (!plan || !creatorSecret || !mode || !rpc) fail('missing bundle fields');

  const ll = plan.launchlab;
  if (ll.program_id !== EXPECTED_PROGRAM_ID) {
    fail(`refusing: plan program ${ll.program_id} != pinned LaunchLab program`);
  }

  const connection = new Connection(rpc, 'confirmed');
  const creator = Keypair.fromSecretKey(Uint8Array.from(creatorSecret));
  const mintKeypair = mintSecret
    ? Keypair.fromSecretKey(Uint8Array.from(mintSecret))
    : Keypair.generate();

  const programId = new PublicKey(ll.program_id);
  const platformId = new PublicKey(ll.platform_id);
  const quoteMint = new PublicKey(plan.quote.mint);
  const mint = mintKeypair.publicKey;
  const mintProgramB = new PublicKey(plan.quote.token_program);
  const curveRuleId = new PublicKey(ll.curve_rule_account.pubkey);

  const { publicKey: poolId } = getPdaLaunchpadPoolId(programId, mint, quoteMint);
  const { publicKey: auth } = getPdaLaunchpadAuth(programId);

  const transferFee = ll.transfer_fee ? {
    transferFeeBasePoints: ll.transfer_fee.transferFeeBasePoints,
    maxinumFee: new BN(ll.transfer_fee.maxinumFee),
  } : undefined;

  let instruction;
  try {
    instruction = initializeWithToken2022(
      programId,
      creator.publicKey,                       // payer
      creator.publicKey,                       // creator: fees are forwarded here
      new PublicKey(ll.config_id),
      platformId,
      auth,
      poolId,
      mint,
      quoteMint,
      getPdaLaunchpadVaultId(programId, poolId, mint).publicKey,
      getPdaLaunchpadVaultId(programId, poolId, quoteMint).publicKey,
      mintProgramB,                            // SDK now takes the quote program directly
      ll.base_decimals,
      plan.token.name, plan.token.symbol, plan.token.metadata_uri,
      {
        type: 'ConstantCurve',
        supply: new BN(ll.supply),
        totalSellA: new BN(ll.total_sell_a),
        totalFundRaisingB: new BN(ll.total_fund_raising_b), // raw, from pricing
        migrateType: 'cpmm',
      },
      new BN(0), new BN(0), new BN(0),          // no vesting
      ll.cpmm_creator_fee_on === 1 ? CpmmCreatorFeeOn.BothToken : CpmmCreatorFeeOn.OnlyTokenB,
      transferFee,
      undefined,                               // platformAllowConfig
      curveRuleId,                             // platformCurveRuleId
    );
  } catch (e) { fail('instruction build failed: ' + e.message); }

  if (!instruction.programId.equals(programId)) fail('instruction targets wrong program');
  const keyStrs = instruction.keys.map((k) => k.pubkey.toBase58());
  if (!keyStrs.includes(platformId.toBase58())) fail('platform id missing from accounts');
  if (!keyStrs.includes(curveRuleId.toBase58())) fail('curve-rule account missing');

  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
  const tx = new Transaction()
    .add(ComputeBudgetProgram.setComputeUnitLimit({ units: 600_000 }))
    .add(instruction);
  tx.recentBlockhash = blockhash;
  tx.lastValidBlockHeight = lastValidBlockHeight;
  tx.feePayer = creator.publicKey;
  tx.sign(creator, mintKeypair);
  if (!tx.verifySignatures()) fail('local signature verification failed');

  const out = {
    ok: true,
    mode,
    mint: mint.toBase58(),
    poolId: poolId.toBase58(),
    creator: creator.publicKey.toBase58(),
    txBytes: tx.serialize().length,
  };

  if (mode === 'dry-run') {
    console.log(JSON.stringify({ ...out, broadcast: false }));
    return;
  }

  // execute: simulate first, then broadcast + confirm
  const sim = await connection.simulateTransaction(tx);
  if (sim.value.err) fail('simulation failed: ' + JSON.stringify(sim.value.err) + ' logs: ' + (sim.value.logs || []).slice(-5).join(' | '));
  const signature = await connection.sendRawTransaction(tx.serialize(), { skipPreflight: false });
  const conf = await connection.confirmTransaction({ signature, blockhash, lastValidBlockHeight }, 'confirmed');
  if (conf.value.err) fail('confirmation error: ' + JSON.stringify(conf.value.err));

  console.log(JSON.stringify({
    ...out,
    broadcast: true,
    signature,
    mintSecret: Array.from(mintKeypair.secretKey), // caller encrypts + stores, never prints
  }));
}

main().catch((e) => fail('fatal: ' + (e && e.message)));
