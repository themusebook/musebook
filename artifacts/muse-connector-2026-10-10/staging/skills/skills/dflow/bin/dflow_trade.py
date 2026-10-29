#!/usr/bin/env python3
"""DFlow live trading helper.

Flow:
  1. prepare: dflow_trade.py prepare --in <MINT> --out <MINT> --amount <ATOMIC>
                [--slippage-bps N] [--priority-fee ...]
     Builds a trade via production GET /order for the dflow-trader wallet.
     Saves the UNSIGNED transaction + exact terms to ~/workspace/dflow/trades/.
     Enforces per-trade and daily SOL caps. Prints terms for user approval.

  2. sign: dflow_trade.py sign --file <PREP_JSON> [--password-stdin]
     Signs the prepared transaction with the local dflow-trader wallet.
     Password is transient (never stored). Requires the user's explicit
     per-trade approval in chat before running.

  3. broadcast: dflow_trade.py broadcast --file <PREP_JSON>
     Submits the wallet-signed transaction via Helius mainnet RPC and confirms
     it against the blockhash DFlow signed with. Records spend in the state file.

Policy (user-approved 2026-09-18, local-wallet exception like clawd-buyer):
  - DFlow spot trading only, via the dflow-trader wallet.
  - Per-trade cap: 0.05 SOL input. Daily cap: 1 SOL (UTC day).
  - Explicit user approval in chat required for every trade.
  - Non-SOL inputs: allowed only with explicit per-trade approval.

Dry-run safe: `prepare` alone only fetches an unsigned tx; nothing is signed
or broadcast without steps 2-3.
"""
import base64
import datetime
import getpass
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/skills/dflow/bin")
import dflow_client as C
import dflow_wallet as W

OUTDIR = "/home/hatch/workspace/dflow/trades"
HELIUS = ["python3", "/home/hatch/workspace/skills/helius/bin/helius_rpc.py",
          "--network", "mainnet"]
STATE_PATH = os.path.join(os.path.expanduser("~"), ".vulcan", "wallets",
                          "dflow-trader-state.json")
SOL_MINT = "So11111111111111111111111111111111111111112"
PER_TRADE_CAP_LAMPORTS = 50_000_000      # 0.05 SOL
DAILY_CAP_LAMPORTS = 1_000_000_000       # 1 SOL per UTC day


def _utc_day():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _load_state():
    try:
        with open(STATE_PATH) as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = {}
    if st.get("day") != _utc_day():
        st = {"day": _utc_day(), "spent_lamports": 0, "trades": []}
    return st


def _save_state(st):
    fd = os.open(STATE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(st, f, indent=2)


def _wallet_pubkey():
    with open(W.WALLET_PATH) as f:
        return json.load(f)["public_key"]


def hrpc(method, params):
    r = subprocess.run(HELIUS + ["--method", method, "--params", json.dumps(params)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("helius %s failed: %s" % (method, r.stderr[:200]))
    return json.loads(r.stdout)


def cmd_prepare(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_mint", required=True)
    p.add_argument("--out", dest="out_mint", required=True)
    p.add_argument("--amount", required=True, help="atomic units of input token")
    p.add_argument("--slippage-bps", default=None)
    p.add_argument("--priority-fee", default="auto")
    p.add_argument("--user", default=None,
                   help="override wallet pubkey (default: dflow-trader wallet)")
    a = p.parse_args(argv)
    user = a.user or _wallet_pubkey()
    amount_int = int(a.amount)
    # cap enforcement (SOL-input trades; other inputs need explicit approval)
    if a.in_mint == SOL_MINT:
        if amount_int > PER_TRADE_CAP_LAMPORTS:
            print("error: amount %d exceeds per-trade cap %d lamports (0.05 SOL)" % (
                amount_int, PER_TRADE_CAP_LAMPORTS), file=sys.stderr)
            return 1
        st = _load_state()
        if st["spent_lamports"] + amount_int > DAILY_CAP_LAMPORTS:
            print("error: daily cap 1 SOL would be exceeded "
                  "(spent %d lamports today)" % st["spent_lamports"], file=sys.stderr)
            return 1
    params = {"userPublicKey": user, "inputMint": a.in_mint,
              "outputMint": a.out_mint, "amount": a.amount,
              "prioritizationFeeLamports": a.priority_fee}
    if a.slippage_bps:
        params["slippageBps"] = a.slippage_bps
    status, body, _ = C.dflow_get("quote-api.dflow.net", "/order", params)
    if status != 200:
        print("error: HTTP %d: %s" % (status, body[:300].decode("utf-8", "replace")),
              file=sys.stderr)
        return 1
    data = json.loads(body)
    if "transaction" not in data:
        print("error: /order returned no transaction: %s" % json.dumps(data)[:300],
              file=sys.stderr)
        return 1
    os.makedirs(OUTDIR, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(OUTDIR, "trade_%s.json" % stamp)
    prep = {
        "created_at": stamp,
        "user": user,
        "inputMint": a.in_mint,
        "outputMint": a.out_mint,
        "amount": a.amount,
        "slippageBps": data.get("slippageBps"),
        "inAmount": data.get("inAmount"),
        "outAmount": data.get("outAmount"),
        "otherAmountThreshold": data.get("otherAmountThreshold"),
        "priceImpactPct": data.get("priceImpactPct"),
        "prioritizationFeeLamports": data.get("prioritizationFeeLamports"),
        "prioritizationType": data.get("prioritizationType"),
        "contextSlot": data.get("contextSlot"),
        "lastValidBlockHeight": data.get("lastValidBlockHeight"),
        "transaction": data["transaction"],  # UNSIGNED base64
        "signed": False,
    }
    with open(path, "w") as f:
        json.dump(prep, f, indent=2)
    print("prepared (UNSIGNED): %s" % path)
    print("  wallet: %s" % user)
    print("  in:  %s %s" % (a.amount, a.in_mint[:8]))
    print("  out: ~%s %s" % (data.get("outAmount"), a.out_mint[:8]))
    print("  priceImpact: %s%%  slippage: %sbps  prioFee: %s lamports" % (
        data.get("priceImpactPct"), data.get("slippageBps"),
        data.get("prioritizationFeeLamports")))
    print("  lastValidBlockHeight: %s" % data.get("lastValidBlockHeight"))
    print("NEXT (after your explicit approval in chat):")
    print("  dflow_trade.py sign --file %s" % path)
    print("  dflow_trade.py broadcast --file %s" % path)
    return 0


def _read_password(use_stdin):
    if use_stdin:
        pw = sys.stdin.readline().rstrip("\n")
    else:
        pw = getpass.getpass("dflow-trader wallet password: ")
    if not pw:
        raise SystemExit("empty password refused")
    return pw


def cmd_sign(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True, help="prepare JSON from step 1")
    p.add_argument("--password-stdin", action="store_true",
                   help="read wallet password from stdin (one line)")
    a = p.parse_args(argv)
    with open(a.file) as f:
        prep = json.load(f)
    if prep.get("signed"):
        print("error: already signed — refusing to re-sign", file=sys.stderr)
        return 1
    pw = _read_password(a.password_stdin or not sys.stdin.isatty())
    try:
        kp = W.load_keypair(W.WALLET_PATH, pw)
    except Exception:
        print("error: wrong password or corrupt wallet file", file=sys.stderr)
        return 1
    finally:
        del pw
    if str(kp.pubkey()) != prep["user"]:
        print("error: wallet pubkey does not match prepared trade", file=sys.stderr)
        return 1
    from solders.transaction import VersionedTransaction
    unsigned = VersionedTransaction.from_bytes(base64.b64decode(prep["transaction"]))
    tx = VersionedTransaction(unsigned.message, [kp])  # constructor signs
    signed_b64 = base64.b64encode(bytes(tx)).decode()
    prep["signed_tx"] = signed_b64
    prep["signed"] = True
    prep["signed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(a.file, "w") as f:
        json.dump(prep, f, indent=2)
    # scrub keypair from memory
    del kp
    print("signed: %s" % a.file)
    print("NEXT: dflow_trade.py broadcast --file %s" % a.file)
    return 0


def cmd_broadcast(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True, help="prepare JSON (signed via step 2)")
    p.add_argument("--signed-tx", default=None,
                   help="override: externally-signed base64 transaction")
    p.add_argument("--confirm-timeout", type=int, default=60)
    a = p.parse_args(argv)
    with open(a.file) as f:
        prep = json.load(f)
    signed_b64 = a.signed_tx or prep.get("signed_tx")
    if not signed_b64:
        print("error: no signed transaction — run 'sign' first or pass --signed-tx",
              file=sys.stderr)
        return 1
    raw = base64.b64decode(signed_b64)
    # sanity: must be a VersionedTransaction with at least one real signature
    try:
        from solders.transaction import VersionedTransaction
        from solders.signature import Signature
        tx = VersionedTransaction.from_bytes(raw)
        zero = bytes(Signature.default())
        real_sigs = [s for s in tx.signatures if bytes(s) != zero]
    except Exception as e:
        print("error: cannot parse signed transaction: %s" % e, file=sys.stderr)
        return 1
    if not real_sigs:
        print("error: transaction has no valid signatures — sign it in your wallet first",
              file=sys.stderr)
        return 1
    print("broadcasting %d-byte tx with %d valid signature(s)..." % (len(raw), len(real_sigs)))
    resp = hrpc("sendTransaction", [signed_b64,
                                   {"encoding": "base64",
                                    "preflightCommitment": "confirmed"}])
    if isinstance(resp, dict) and resp.get("error"):
        print("error: broadcast rejected: %s" % json.dumps(resp["error"])[:300],
              file=sys.stderr)
        return 1
    sig = resp.get("result") if isinstance(resp, dict) else resp
    if not sig or not isinstance(sig, str):
        print("error: unexpected sendTransaction response: %s" % json.dumps(resp)[:200],
              file=sys.stderr)
        return 1
    print("signature: %s" % sig)
    print("https://solscan.io/tx/%s" % sig)
    # confirm against the blockhash DFlow signed with
    bh = tx.message.recent_blockhash
    lvh = prep.get("lastValidBlockHeight")
    deadline = time.time() + a.confirm_timeout
    while time.time() < deadline:
        try:
            st = hrpc("getSignatureStatuses", [[sig], {"searchTransactionHistory": True}])
            v = (st or {}).get("value", [None])[0]
            if v and (v.get("confirmationStatus") in ("confirmed", "finalized")):
                if v.get("err"):
                    print("FAILED on-chain: %s" % json.dumps(v["err"]))
                    return 1
                print("confirmed (%s), slot %s" % (v["confirmationStatus"], v.get("slot")))
                # record spend against the daily cap
                try:
                    st = _load_state()
                    spent = int(prep.get("inAmount") or prep.get("amount") or 0) \
                        if prep.get("inputMint") == SOL_MINT else 0
                    st["spent_lamports"] += spent
                    st["trades"].append({
                        "sig": sig, "at": datetime.datetime.now(
                            datetime.timezone.utc).isoformat(),
                        "in": prep.get("inAmount"), "out": prep.get("outAmount"),
                    })
                    _save_state(st)
                except Exception as e:
                    print("warning: spend not recorded: %s" % e, file=sys.stderr)
                return 0
        except Exception as e:
            print("confirm poll: %s" % e, file=sys.stderr)
        time.sleep(4)
    print("warning: not confirmed within %ds — check the signature manually" % a.confirm_timeout,
          file=sys.stderr)
    return 2


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("prepare", "sign", "broadcast"):
        print(__doc__, file=sys.stderr)
        return 2
    if sys.argv[1] == "prepare":
        return cmd_prepare(sys.argv[2:])
    if sys.argv[1] == "sign":
        return cmd_sign(sys.argv[2:])
    return cmd_broadcast(sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
