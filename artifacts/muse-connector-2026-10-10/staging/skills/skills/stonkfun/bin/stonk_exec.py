#!/usr/bin/env python3
"""Execute a Stonkfun LaunchLab launch from a plan file.

Scoped local wallet: stonk-launcher (user-approved 2026-09-18).
Launches ONLY: initialize_with_token2022 on the pinned LaunchLab program.

Usage:
  stonk_exec.py --plan state/launches/<name>.plan.json --dry-run
      # build + locally sign the full transaction, do NOT broadcast.
  stonk_exec.py --plan <plan> --confirm
      # simulate, broadcast, confirm. Needs explicit chat approval of the
      # exact terms first; --confirm is the in-command second factor.

Policy (enforced here):
  - Program id pinned to the LaunchLab program; anything else refuses.
  - Per-launch cost cap 0.10 SOL (rent + fees; no launch fee on this path).
  - Daily cap 1 SOL (UTC), tracked in state/launcher_spend.json.
  - Wallet password transient (getpass or --password-stdin); never stored.
  - Mint keypair is encrypted with the wallet password and stored at
    state/launches/<mint>.mint.json (0600) — it is the token's mint
    authority key, needed to revoke authorities later.
"""
import base64
import datetime
import getpass
import json
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCH_DIR = os.path.join(SKILL_DIR, "bin", "launch")
EXEC_JS = os.path.join(LAUNCH_DIR, "stonk_exec.mjs")
WALLET_PATH = os.environ.get("STONK_WALLET_PATH") or os.path.join(
    os.path.expanduser("~"), ".vulcan", "wallets", "stonk-launcher.json")
SPEND_PATH = os.path.join(SKILL_DIR, "state", "launcher_spend.json")
LAUNCHES_PATH = os.path.join(SKILL_DIR, "state", "launches.json")

PINNED_PROGRAM = "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"
PER_LAUNCH_CAP_SOL = 0.10
DAILY_CAP_SOL = 1.0
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


def rpc_call(rpc, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    r = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-X", "POST", rpc,
         "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, text=True, timeout=40)
    return json.loads(r.stdout)


def get_balance_sol(rpc, pubkey):
    d = rpc_call(rpc, "getBalance", [pubkey])
    return d["result"]["value"] / 1e9


def load_spend():
    if os.path.exists(SPEND_PATH):
        return json.load(open(SPEND_PATH))
    return {}


def save_spend(s):
    os.makedirs(os.path.dirname(SPEND_PATH), exist_ok=True)
    json.dump(s, open(SPEND_PATH, "w"), indent=2)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--password-stdin", action="store_true")
    ap.add_argument("--rpc", default=os.environ.get("STONK_RPC") or DEFAULT_RPC)
    ns = ap.parse_args()

    if not ns.dry_run and not ns.confirm:
        print("Refusing: live launch needs --confirm (and the user's chat approval of exact terms).")
        print("Use --dry-run to build + sign locally without broadcasting.")
        return 2

    plan = json.load(open(ns.plan))
    ll = plan.get("launchlab", {})
    if ll.get("program_id") != PINNED_PROGRAM:
        print(f"Refusing: plan program {ll.get('program_id')} != pinned LaunchLab program.")
        return 2

    if not os.path.exists(WALLET_PATH):
        print(f"No stonk-launcher wallet at {WALLET_PATH}. Create it with stonk_wallet.py first.")
        return 2
    w = json.load(open(WALLET_PATH))
    if "--password-stdin" in sys.argv or ns.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("stonk-launcher wallet password: ")
    if not password:
        print("No password; aborting.")
        return 2

    sys.path.insert(0, os.path.join(SKILL_DIR, "bin"))
    from stonk_wallet import decrypt_secret
    try:
        secret = decrypt_secret(w["encrypted"], password)
    except Exception:
        print("Wrong password (decrypt failed).")
        return 2
    if len(secret) != 64:
        print("Decrypted secret has wrong length; aborting.")
        return 2

    # Daily cap (UTC).
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    spend = load_spend()
    day_spend = spend.get(today, 0.0)
    if day_spend + PER_LAUNCH_CAP_SOL > DAILY_CAP_SOL:
        print(f"Refusing: today's spend {day_spend:.4f} + cap {PER_LAUNCH_CAP_SOL} > daily {DAILY_CAP_SOL} SOL.")
        return 2

    mode = "dry-run" if ns.dry_run else "execute"
    creator_pubkey = w["public_key"]
    bal_before = None
    if mode == "execute":
        bal_before = get_balance_sol(ns.rpc, creator_pubkey)
        if bal_before < PER_LAUNCH_CAP_SOL:
            print(f"Refusing: wallet balance {bal_before:.4f} SOL < per-launch cap {PER_LAUNCH_CAP_SOL} SOL. Fund {creator_pubkey} first.")
            return 2

    bundle = {
        "plan": plan,
        "creatorSecret": list(secret),
        "mintSecret": None,  # fresh mint keypair per launch
        "mode": mode,
        "rpc": ns.rpc,
    }
    # Wipe the secret from this process ASAP after piping.
    bundle_json = json.dumps(bundle)
    secret = b"\x00" * 64
    del secret

    r = subprocess.run(["node", EXEC_JS], input=bundle_json, capture_output=True,
                       text=True, timeout=180, cwd=LAUNCH_DIR)
    bundle_json = "x" * len(bundle_json)
    del bundle_json
    if r.returncode != 0:
        print("Executor failed:")
        print((r.stdout or "")[-800:])
        print((r.stderr or "")[-800:])
        return 1
    try:
        out = json.loads(r.stdout)
    except Exception:
        print("Executor returned unparsable output:")
        print(r.stdout[-800:])
        return 1
    if not out.get("ok"):
        print(f"Executor error: {out.get('error')}")
        return 1

    print(json.dumps({k: v for k, v in out.items() if k != "mintSecret"}, indent=2))

    if mode == "execute":
        # Encrypt + store the mint authority key (needed to revoke authorities later).
        from stonk_wallet import encrypt_secret
        mint_secret = bytes(out["mintSecret"])
        mint_path = os.path.join(SKILL_DIR, "state", "launches", f"{out['mint']}.mint.json")
        with open(mint_path, "w") as f:
            json.dump({"mint": out["mint"], "pool": out["poolId"],
                       "encrypted": encrypt_secret(mint_secret, password)}, f, indent=2)
        os.chmod(mint_path, 0o600)
        mint_secret = b"\x00" * 64

        # Spend accounting (balance delta).
        bal_after = get_balance_sol(ns.rpc, creator_pubkey)
        cost = max(0.0, (bal_before or 0) - bal_after)
        spend[today] = round(day_spend + cost, 6)
        save_spend(spend)
        if cost > PER_LAUNCH_CAP_SOL:
            print(f"WARNING: actual cost {cost:.4f} SOL exceeded per-launch cap {PER_LAUNCH_CAP_SOL} — logged for review.")

        launches = json.load(open(LAUNCHES_PATH)) if os.path.exists(LAUNCHES_PATH) else []
        launches.append({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         "mint": out["mint"], "pool": out["poolId"],
                         "signature": out["signature"], "plan": ns.plan,
                         "cost_sol": round(cost, 6)})
        json.dump(launches, open(LAUNCHES_PATH, "w"), indent=2)
        print(f"\nNext: stonk_launch.py check --mint {out['mint']}  (adoption in ~1-2 min)")
        print(f"Mint authority key stored encrypted at {mint_path}")
    password = "x" * len(password)
    del password
    return 0


if __name__ == "__main__":
    sys.exit(main())
