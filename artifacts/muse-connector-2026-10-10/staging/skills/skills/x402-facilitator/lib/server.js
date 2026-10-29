// Express app: x402 + x402m endpoints for a self-hosted facilitator.
// Non-custodial: the facilitator verifies and relays. The payer signs.
import express from "express";
import { resolveNetwork, BATCH_MAX_ITEMS } from "./config.js";
import { buildBatchPlan, verifyBatchTx, settleBatchTx } from "./solana.js";
import { verifyEvmExact, settleEvmAuthorization } from "./evm.js";

export function createApp(cfg) {
  const app = express();
  app.use(express.json({ limit: "2mb" }));

  const receipts = []; // x402:receipt:<sig> -> receipt
  const pulse = {
    startedAt: Date.now(),
    settlements: 0,
    batchSettlements: 0,
    volumeBaseUnits: 0n,
    referrers: new Map(),
    pairs: new Map(),
  };

  const baseUrl = (cfg.baseUrl || `http://localhost:${cfg.port || 8787}`).replace(/\/$/, "");

  // ---- tiny per-IP rate limiter (v0; use a real one in production) ----
  const buckets = new Map();
  function rateLimit(max, windowMs) {
    return (req, res, next) => {
      const ip = req.ip || "unknown";
      const now = Date.now();
      const b = buckets.get(ip) || { count: 0, reset: now + windowMs };
      if (now > b.reset) { b.count = 0; b.reset = now + windowMs; }
      b.count += 1;
      buckets.set(ip, b);
      if (b.count > max) return res.status(429).json({ ok: false, error: "rate_limited" });
      next();
    };
  }

  function recordReceipt({ network, batch, payer, items, tx, ref, private: isPrivate }) {
    pulse.settlements += 1;
    if (batch) pulse.batchSettlements += 1;
    let vol = 0n;
    for (const it of items) {
      vol += BigInt(it.amount || "0");
      const pair = `${payer}->${it.payTo}`;
      pulse.pairs.set(pair, (pulse.pairs.get(pair) || 0n) + BigInt(it.amount || "0"));
    }
    pulse.volumeBaseUnits += vol;
    if (ref) pulse.referrers.set(ref, (pulse.referrers.get(ref) || 0n) + vol);
    const receipt = {
      id: `x402:receipt:${tx}`,
      ts: Date.now(),
      network,
      facilitator: cfg.id,
      batch,
      payer,
      items,
      tx,
      ref: ref || null,
    };
    if (!isPrivate) receipts.unshift(receipt);
    if (receipts.length > 500) receipts.length = 500;
    return receipt;
  }

  const descriptor = () => ({
    x402m: "v0",
    id: cfg.id,
    operator: cfg.operator || "unknown",
    description: "Non-custodial x402 facilitator with single-signature batch settlement (x402m meta protocol)",
    endpoints: {
      supported: `${baseUrl}/api/x402/supported`,
      verify: `${baseUrl}/api/x402/verify`,
      settle: `${baseUrl}/api/x402/settle`,
      batchPlan: `${baseUrl}/api/x402/batch/plan`,
      batchVerify: `${baseUrl}/api/x402/batch/verify`,
      batchSettle: `${baseUrl}/api/x402/batch/settle`,
      batchSettleMulti: `${baseUrl}/api/x402/batch/settle-multi`,
      receipts: `${baseUrl}/api/x402/receipts`,
      pulse: `${baseUrl}/api/x402/pulse`,
      facilitators: `${baseUrl}/api/x402/facilitators`,
    },
    networks: cfg.networks,
    extensions: ["x402m-batch-v0", "x402m-receipts-v0", "x402m-referral-v0"],
  });

  // ---- discovery ----
  app.get("/.well-known/x402-facilitator", (req, res) => res.json(descriptor()));

  app.get("/api/x402/supported", (req, res) => {
    const kinds = [];
    for (const n of cfg.networks) {
      const r = resolveNetwork(n);
      if (!r) continue;
      kinds.push({ x402Version: 1, scheme: "exact", network: r.caip });
      if (r.net.kind === "solana")
        kinds.push({ x402Version: 1, scheme: "exact", network: r.caip, extension: "x402m-batch-v0" });
      else
        kinds.push({ x402Version: 1, scheme: "exact", network: r.caip, extension: "x402m-evm-relay-v0" });
    }
    res.json({ ok: true, facilitator: cfg.id, kinds });
  });

  app.get("/api/x402/batch/ping", (req, res) =>
    res.json({ ok: true, x402m: "v0", facilitator: cfg.id, ts: Date.now() }));

  // ---- batch plan (Solana only; EVM signs client-side per x402 exact) ----
  app.post("/api/x402/batch/plan", rateLimit(30, 60000), async (req, res) => {
    try {
      const { network, payer, payments, ref, private: isPrivate } = req.body || {};
      const r = resolveNetwork(network);
      if (!r) return res.status(400).json({ ok: false, error: "unsupported_network" });
      if (r.net.kind !== "solana")
        return res.status(400).json({
          ok: false,
          error: "evm_no_plan",
          note: "EVM exact signs an EIP-712 authorization client-side; send it to /api/x402/batch/settle-multi",
        });
      const plan = await buildBatchPlan(r.net, { payer, payments, ref });
      plan.payer = payer;
      plan.private = !!isPrivate;
      res.json(plan);
    } catch (e) {
      res.status(e.status || 500).json({ ok: false, error: String(e.message || e).slice(0, 200) });
    }
  });

  // ---- batch verify (Solana) ----
  app.post("/api/x402/batch/verify", rateLimit(60, 60000), (req, res) => {
    try {
      const { network, paymentHeader, plan } = req.body || {};
      const r = resolveNetwork(network);
      if (!r || r.net.kind !== "solana")
        return res.status(400).json({ isValid: false, invalidReason: "unsupported_network (batch verify v0: solana only)" });
      const v = verifyBatchTx(r.net, paymentHeader, plan);
      res.json(v);
    } catch (e) {
      res.status(e.status || 400).json({ isValid: false, invalidReason: String(e.message || e).slice(0, 160) });
    }
  });

  // ---- batch settle (Solana): one signature, one tx, N payments ----
  app.post("/api/x402/batch/settle", rateLimit(10, 60000), async (req, res) => {
    try {
      const { network, paymentHeader, plan, ref, private: isPrivate } = req.body || {};
      const r = resolveNetwork(network);
      if (!r || r.net.kind !== "solana")
        return res.status(400).json({ ok: false, error: "unsupported_network (batch v0: solana only)" });
      const v = verifyBatchTx(r.net, paymentHeader, plan);
      const { signature, confirmed } = await settleBatchTx(r.net, paymentHeader);
      const receipt = recordReceipt({
        network: r.caip, batch: true, payer: v.payer, items: v.items,
        tx: signature, ref: ref || plan?.ref, private: isPrivate,
      });
      res.json({
        success: true, transaction: signature, network: r.caip, payer: v.payer,
        items: v.items.map((i) => ({ ...i, status: "settled" })),
        confirmed, receipt: receipt.id,
      });
    } catch (e) {
      res.status(e.status || 500).json({ ok: false, error: String(e.message || e).slice(0, 200) });
    }
  });

  // ---- settle-multi: N envelopes, possibly multi-payer / mixed chains ----
  app.post("/api/x402/batch/settle-multi", rateLimit(10, 60000), async (req, res) => {
    const payments = Array.isArray(req.body?.payments) ? req.body.payments : [];
    if (!payments.length || payments.length > 16)
      return res.status(400).json({ ok: false, error: "payments must be 1-16 envelopes" });
    const results = [];
    const settled = [];
    for (let i = 0; i < payments.length; i++) {
      const p = payments[i] || {};
      const r = resolveNetwork(p.network || p.paymentRequirements?.network);
      if (!r) { results.push({ index: i, success: false, error: "unsupported_network" }); continue; }
      try {
        if (r.net.kind === "solana") {
          const plan = p.plan || null;
          const v = verifyBatchTx(r.net, p.paymentHeader, plan);
          const { signature, confirmed } = await settleBatchTx(r.net, p.paymentHeader);
          results.push({ index: i, success: true, phase: "settled", network: r.caip, transaction: signature, confirmed });
          settled.push({ sig: signature, network: r.caip, payer: v.payer, items: v.items });
        } else {
          // EVM: standard x402 exact payload (EIP-712 over EIP-3009)
          const req2 = { ...(p.paymentRequirements || {}) };
          if (!req2.network) req2.network = r.caip;
          const v = await verifyEvmExact(r.net, p.paymentPayload, req2);
          const { hash, confirmed } = await settleEvmAuthorization(r.net, v);
          results.push({ index: i, success: true, phase: "settled", network: r.caip, transaction: hash, confirmed });
          settled.push({ sig: hash, network: r.caip, payer: v.from, items: [{ payTo: v.to, asset: r.net.usdc, amount: v.value }] });
        }
      } catch (e) {
        results.push({ index: i, success: false, error: String(e.message || e).slice(0, 160), status: e.status || undefined });
      }
    }
    let receipt = null;
    if (settled.length) {
      const items = settled.flatMap((s) => s.items);
      receipt = recordReceipt({
        network: "multi", batch: true,
        payer: settled.map((s) => s.payer).join(","),
        items, tx: settled.map((s) => s.sig).join(","),
        ref: req.body?.ref, private: req.body?.private,
      }).id;
    }
    res.json({ ok: true, results, receipt });
  });

  // ---- single x402 verify/settle (Solana exact) ----
  app.post("/api/x402/verify", rateLimit(60, 60000), (req, res) => {
    try {
      const { paymentHeader, paymentRequirements } = req.body || {};
      const r = resolveNetwork(paymentRequirements?.network);
      if (!r || r.net.kind !== "solana")
        return res.status(400).json({ isValid: false, invalidReason: "unsupported_network (kit v0: solana single)" });
      const plan = {
        payer: undefined,
        items: [{ payTo: paymentRequirements.payTo, asset: r.net.usdc, amount: paymentRequirements.maxAmountRequired }],
      };
      const v = verifyBatchTx(r.net, paymentHeader, plan);
      res.json({ isValid: true, payer: v.payer });
    } catch (e) {
      res.status(400).json({ isValid: false, invalidReason: String(e.message || e).slice(0, 160) });
    }
  });

  app.post("/api/x402/settle", rateLimit(10, 60000), async (req, res) => {
    try {
      const { paymentHeader, paymentRequirements } = req.body || {};
      const r = resolveNetwork(paymentRequirements?.network);
      if (!r || r.net.kind !== "solana")
        return res.status(400).json({ success: false, error: "unsupported_network (kit v0: solana single)" });
      const { signature, confirmed } = await settleBatchTx(r.net, paymentHeader);
      const receipt = recordReceipt({
        network: r.caip, batch: false, payer: "unknown",
        items: [{ payTo: paymentRequirements.payTo, asset: r.net.usdc, amount: paymentRequirements.maxAmountRequired }],
        tx: signature, ref: req.body?.ref, private: req.body?.private,
      });
      res.json({ success: true, transaction: signature, network: r.caip, confirmed, receipt: receipt.id });
    } catch (e) {
      res.status(e.status || 500).json({ success: false, error: String(e.message || e).slice(0, 200) });
    }
  });

  // ---- receipts + pulse (the public m2m tape) ----
  app.get("/api/x402/receipts", (req, res) => {
    const limit = Math.min(parseInt(req.query.limit || "50", 10) || 50, 200);
    res.json({ ok: true, facilitator: cfg.id, count: Math.min(limit, receipts.length), receipts: receipts.slice(0, limit) });
  });

  app.get("/api/x402/pulse", (req, res) => {
    const topPairs = [...pulse.pairs.entries()]
      .sort((a, b) => (b[1] > a[1] ? 1 : -1)).slice(0, 10)
      .map(([pair, volume]) => ({ pair, volume: volume.toString() }));
    const topReferrers = [...pulse.referrers.entries()]
      .sort((a, b) => (b[1] > a[1] ? 1 : -1)).slice(0, 10)
      .map(([ref, volume]) => ({ ref, volume: volume.toString() }));
    res.json({
      ok: true, window: "24h", facilitator: cfg.id,
      settlements: pulse.settlements,
      batchSettlements: pulse.batchSettlements,
      volumeBaseUnits: pulse.volumeBaseUnits.toString(),
      topPairs, topReferrers,
    });
  });

  // ---- registry: this facilitator (federation forwarding is a v1 item) ----
  app.get("/api/x402/facilitators", (req, res) => {
    res.json({ ok: true, facilitators: [{ ...descriptor(), self: true }] });
  });

  app.get("/", (req, res) => res.json({ ok: true, ...descriptor() }));

  return app;
}
