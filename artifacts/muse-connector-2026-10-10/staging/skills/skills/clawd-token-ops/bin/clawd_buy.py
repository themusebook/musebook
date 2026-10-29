#!/usr/bin/env python3
"""Clawd buyer — agent-executed SOL -> $CLAWD swaps via Jupiter.

Policy (user-approved 2026-09-17):
- Buy-only: inputMint must be native SOL, outputMint must be the $CLAWD mint.
- Per-buy cap: 0.0169420 SOL (16,942,000 lamports).
- Per-day cap:  1 SOL (1,000,000,000 lamports). Day boundary = UTC.
- Every buy requires explicit user approval in chat; this script additionally
  requires --confirm to execute. Without --confirm it only quotes+signs.

Usage:
  clawd_buy.py quote --sol 0.01          # quote only, no signing, no spend
  clawd_buy.py buy --sol 0.01 --confirm  # execute after user approval in chat
  clawd_buy.py status                    # address, daily spend remaining

Auth: Jupiter calls go through ~/workspace/skills/jupiter/bin/jup.py which
attaches the stored custom.jupiter credential via surrogate. Never prints keys.
"""
import argparse
import base64
import datetime
import json
import os
import subprocess
import sys
import time

SOL_MINT = "So11111111111111111111111111111111111111112"
CLAWD_MINT = "8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump"
PER_BUY_LAMPORTS = 16_942_000      # 0.0169420 SOL
PER_DAY_LAMPORTS = 1_000_000_000   # 1 SOL
SLIPPAGE_BPS = 100                 # 1%

HOME = os.path.expanduser("~")
WALLET_PATH = os.path.join(HOME, ".vulcan", "wallets", "clawd-buyer.json")
STATE_PATH = os.path.join(HOME, ".vulcan", "wallets", "clawd-buyer-state.json")
JUP = os.path.join(HOME, "workspace", "skills", "jupiter", "bin", "jup.py")


def load_keypair():
    from solders.keypair import Keypair
    with open(WALLET_PATH) as f:
        data = json.load(f)
    kp = Keypair.from_bytes(bytes(data["secret"]))
    assert str(kp.pubkey()) == data["public_key"], "keypair verification failed"
    return kp, data["public_key"]


def today_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def load_state():
    try:
        with open(STATE_PATH) as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = {}
    if st.get("day") != today_utc():
        st = {"day": today_utc(), "spent_lamports": 0}
    return st


def save_state(st):
    fd = os.open(STATE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(st, f)


def check_caps(amount_lamports, override_cap=False):
    if amount_lamports <= 0:
        return "amount must be positive"
    if not override_cap and amount_lamports > PER_BUY_LAMPORTS:
        return (f"per-buy cap exceeded: {amount_lamports} > {PER_BUY_LAMPORTS} "
                f"lamports (0.0169420 SOL)")
    st = load_state()
    if st["spent_lamports"] + amount_lamports > PER_DAY_LAMPORTS:
        return (f"per-day cap exceeded: already spent {st['spent_lamports']}, "
                f"cap is {PER_DAY_LAMPORTS} lamports (1 SOL/day)")
    return None


def jup_get(path):
    r = subprocess.run([sys.executable, JUP, "GET", path],
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout)


def jup_post(path, data):
    r = subprocess.run([sys.executable, JUP, "POST", path, "--data",
                        json.dumps(data)],
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout)


def get_order(amount_lamports, taker):
    path = ("/swap/v2/order?inputMint=" + SOL_MINT +
            "&outputMint=" + CLAWD_MINT +
            "&amount=" + str(amount_lamports) +
            "&taker=" + taker +
            "&slippageBps=" + str(SLIPPAGE_BPS))
    return jup_get(path)


def sign_order(order, kp):
    from solders.transaction import VersionedTransaction
    raw = base64.b64decode(order["transaction"])
    utx = VersionedTransaction.from_bytes(raw)
    # Sign the canonical wire message bytes. NOTE: solders 0.29's
    # bytes(utx.message) drops the 0x80 version prefix, producing a
    # signature that verifies locally but fails on-chain (SignatureFailure).
    n = raw[0]
    wire_msg = raw[1 + 64 * n:]
    sig = kp.sign_message(wire_msg)
    return base64.b64encode(bytes([n]) + bytes(sig) + wire_msg).decode()


def cmd_quote(args):
    amount = int(round(args.sol * 1_000_000_000))
    err = check_caps(amount)
    if err:
        print(json.dumps({"ok": False, "error": err}))
        return 1
    _, pubkey = load_keypair()
    order = get_order(amount, pubkey)
    if "transaction" not in order:
        print(json.dumps({"ok": False, "error": "no transaction in order",
                          "order": order}))
        return 1
    out = {
        "ok": True,
        "in_sol": args.sol,
        "in_lamports": amount,
        "taker": pubkey,
        "requestId": order.get("requestId"),
        "quote": {k: order.get(k) for k in
                   ("inputMint", "outputMint", "inAmount", "outAmount",
                    "priceImpactPct", "slippageBps", "routePlan")},
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_buy(args):
    amount = int(round(args.sol * 1_000_000_000))
    err = check_caps(amount, override_cap=getattr(args, "override_cap", False))
    if err:
        print(json.dumps({"ok": False, "error": err}))
        return 1
    if not args.confirm:
        print(json.dumps({"ok": False,
                          "error": "refusing without --confirm (needs user approval in chat)"}))
        return 1
    # idempotency guard: refuse a repeat buy of the same amount within 10 min
    # unless --force is passed. Prevents accidental double-buys from re-runs.
    st = load_state()
    last = st.get("last_buy") or {}
    now = time.time()
    if (not getattr(args, "force", False)
            and last.get("sol_lamports") == amount
            and now - float(last.get("ts", 0)) < 600):
        print(json.dumps({"ok": False,
                          "error": "duplicate buy blocked: same amount %.9f SOL executed %d seconds ago (sig %s). Re-run with --force if this is intentional."
                                   % (amount / 1_000_000_000,
                                      int(now - float(last.get("ts", 0))),
                                      last.get("signature", "?"))}))
        return 1
    kp, pubkey = load_keypair()
    order = get_order(amount, pubkey)
    if "transaction" not in order or "requestId" not in order:
        print(json.dumps({"ok": False, "error": "bad order response",
                          "order": order}))
        return 1
    signed = sign_order(order, kp)
    res = jup_post("/swap/v2/execute",
                   {"signedTransaction": signed,
                    "requestId": order["requestId"]})
    ok = res.get("status") == "Success" or "signature" in res
    if ok:
        st = load_state()
        st["spent_lamports"] += amount
        st["last_buy"] = {"sol_lamports": amount,
                          "signature": res.get("signature", ""),
                          "ts": time.time()}
        save_state(st)
        # post the buy to the site (musebook buy history, KV-backed)
        try:
            sig = res.get("signature", "")
            subprocess.run(
                [sys.executable,
                 os.path.join(HOME, "workspace", "musebook", "cloudflare",
                              "bin", "record_buy.py"),
                 "--sol", str(amount / 1_000_000_000),
                 "--clawd", str(float(order.get("outAmount", 0)) / 1_000_000),
                 "--tx", sig],
                capture_output=True, text=True, timeout=90)
        except Exception:
            pass
    print(json.dumps({"ok": ok,
                      "in_lamports": amount,
                      "spent_today_lamports": load_state()["spent_lamports"],
                      "result": res}, indent=2))
    return 0 if ok else 1


def cmd_status(_args):
    _, pubkey = load_keypair()
    st = load_state()
    print(json.dumps({
        "address": pubkey,
        "fund_this_address_with_SOL": True,
        "day_utc": st["day"],
        "spent_lamports": st["spent_lamports"],
        "remaining_lamports": PER_DAY_LAMPORTS - st["spent_lamports"],
        "per_buy_lamports": PER_BUY_LAMPORTS,
        "per_day_lamports": PER_DAY_LAMPORTS,
        "policy": "buy-only SOL -> $CLAWD; explicit user approval per buy",
    }, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quote")
    q.add_argument("--sol", type=float, required=True)
    b = sub.add_parser("buy")
    b.add_argument("--sol", type=float, required=True)
    b.add_argument("--confirm", action="store_true")
    b.add_argument("--force", action="store_true",
                   help="allow a repeat buy of the same amount within 10 min of the last one")
    b.add_argument("--override-cap", action="store_true",
                   help="one-time override of the per-buy cap (per-day cap still enforced);"
                        " only for explicit user-approved one-off buys")
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "quote":
        return cmd_quote(args)
    if args.cmd == "buy":
        return cmd_buy(args)
    return cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
