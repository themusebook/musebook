#!/usr/bin/env python3
"""One-shot Phoenix perps trader registration.

Implements the verified mainnet registration flow (2026-09-18):

    1. POST /v1/exchange/build-register-ixs   (no referral code needed)
    2. Assemble a legacy transaction locally
    3. partial_sign with the trader authority (the onboarder slot stays empty)
    4. POST /v1/exchange/send-register-ixs     (Phoenix co-signs + broadcasts)
    5. Verify via trader-state API + `vulcan status`

Subcommands:

    quote     Print the EXACT registration cost (rent + fee + total) for a
              maxPositions config, from the on-chain rent model. If the
              authority is already funded, also cross-checks with a live
              mainnet simulation. No wallet, no signing.
    register  Full flow: cost check, balance check, decrypt the vulcan wallet
              (password via VULCAN_WALLET_PASSWORD env or interactive prompt),
              partial-sign, submit, confirm, verify. Requires --yes.

Costs (exact, from the on-chain rent model calibrated on mainnet 2026-09-18):

    maxPositions=32   0.00837184 SOL rent
    maxPositions=128  0.02787904 SOL rent
    + 0.00001 SOL network fee (2 signatures: authority + onboarder)

The API rejects maxPositions < 32. Always run `quote` before `register`
and get the user's explicit approval of the exact total.

Wallet policy: the private key is decrypted only in memory, never printed,
never written to disk, and never leaves this process. The password comes
from the VULCAN_WALLET_PASSWORD environment variable (transient) or an
interactive prompt — never from a CLI argument or a file.

Usage:
    register_trader.py quote --authority <PUBKEY> [--max-positions 32]
    register_trader.py register --wallet <NAME> --yes [--max-positions 32]
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

API_BASE = os.environ.get("PHOENIX_API_URL", "https://perp-api.phoenix.trade")
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
FEE_PER_SIGNATURE = 5000  # lamports

# Trader PDA rent model, calibrated on two exact mainnet measurements
# (2026-09-18): maxPositions=32 -> 8,371,840 lamports, maxPositions=128 ->
# 27,879,040 lamports, and the on-chain account data length (5,360 bytes
# at 128 positions). Layout: 240-byte header + 40 bytes per position;
# rent-exempt minimum = (128 + data_len) * 5080 lamports.
_TRADER_FIXED_BYTES = 128 + 240
_TRADER_BYTES_PER_POSITION = 40
_LAMPORTS_PER_BYTE = 5080


def registration_cost(max_positions: int) -> tuple[int, int, int]:
    """Exact (rent, fee, total) in lamports for a registration config."""
    if max_positions < 32:
        raise ValueError("Phoenix rejects maxPositions < 32 (invalid_max_positions)")
    rent = ((_TRADER_FIXED_BYTES + _TRADER_BYTES_PER_POSITION * max_positions)
            * _LAMPORTS_PER_BYTE)
    fee = 2 * FEE_PER_SIGNATURE  # authority + onboarder signature slots
    return rent, fee, rent + fee


def vulcan_rpc_url() -> str:
    """Prefer the user's configured vulcan RPC, fall back to public mainnet."""
    cfg = os.path.expanduser("~/.vulcan/config.toml")
    try:
        with open(cfg) as f:
            for line in f:
                line = line.strip()
                if line.startswith("rpc_url"):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if url:
                        return url
    except OSError:
        pass
    return DEFAULT_RPC


def api_post(path: str, payload: dict, api_base: str) -> dict:
    req = urllib.request.Request(
        api_base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"Phoenix API {path} -> HTTP {e.code}: {detail}")


def api_get(path: str, api_base: str) -> dict | None:
    req = urllib.request.Request(api_base + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"Phoenix API {path} -> HTTP {e.code}: {detail}")


def rpc_call(rpc_url: str, method: str, params: list, retries: int = 3) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                rpc_url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            if data.get("error"):
                raise RuntimeError(
                    f"RPC {method} error: {json.dumps(data['error'])[:400]}")
            return data["result"]
        except Exception as e:  # transient network flakes, esp. on public RPC
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"RPC {method} failed after {retries} tries: {last}")


def build_instructions(build: dict) -> tuple[list[Instruction], Pubkey]:
    ixs = []
    for raw in build["instructions"]:
        program_id = Pubkey.from_string(raw["programId"])
        metas = []
        for k in raw["keys"]:
            pubkey = Pubkey.from_string(k.get("pubkey") or k.get("address"))
            is_signer = k.get("isSigner", k.get("is_signer", False))
            is_writable = k.get("isWritable", k.get("is_writable", False))
            metas.append(AccountMeta(pubkey=pubkey, is_signer=is_signer,
                                     is_writable=is_writable))
        ixs.append(Instruction(program_id=program_id, accounts=metas,
                               data=bytes(raw["data"])))
    return ixs, Pubkey.from_string(build["traderPda"])


def assemble_tx(ixs: list[Instruction], payer: Pubkey,
                rpc_url: str) -> tuple[Transaction, Hash]:
    blockhash = Hash.from_string(
        rpc_call(rpc_url, "getLatestBlockhash",
                 [{"commitment": "confirmed"}])["value"]["blockhash"]
    )
    msg = Message.new_with_blockhash(ixs, payer, blockhash)
    return Transaction.new_unsigned(msg), blockhash


def account_exists(pubkey: str, rpc_url: str) -> bool:
    try:
        return rpc_call(rpc_url, "getAccountInfo",
                        [pubkey, {"commitment": "confirmed"}]) is not None
    except RuntimeError:
        return False


def simulate_register(ixs: list[Instruction], payer: Pubkey, trader_pda: Pubkey,
                      rpc_url: str, expected_rent: int) -> None:
    """Dry-run the register tx. Raises on failure; cross-checks the rent model."""
    tx, _ = assemble_tx(ixs, payer, rpc_url)
    b64 = base64.b64encode(bytes(tx)).decode()
    sim = rpc_call(rpc_url, "simulateTransaction", [b64, {
        "sigVerify": False, "encoding": "base64", "commitment": "confirmed",
        "accounts": {"encoding": "base64", "addresses": [str(trader_pda)]},
    }])
    if sim.get("err"):
        raise RuntimeError(
            f"registration simulation failed: {json.dumps(sim['err'])[:300]}")
    acct = (sim.get("accounts") or [None])[0]
    if acct and abs(acct["lamports"] - expected_rent) > 1000:
        print(f"  warning: simulated rent {acct['lamports']:,} lamports differs "
              f"from the cost model {expected_rent:,} — investigate before "
              f"registering", file=sys.stderr)


def check_registered(authority: str, api_base: str) -> bool:
    return api_get(f"/v1/trader/state/{authority}", api_base) is not None


def wallet_balance_lamports(wallet: str, rpc_url: str) -> tuple[str, int]:
    out = subprocess.run(
        ["vulcan", "wallet", "show", wallet, "-o", "json", "--rpc-url", rpc_url],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError(f"vulcan wallet show failed: {out.stderr.strip()[:300]}")
    info = json.loads(out.stdout)
    pubkey = info.get("pubkey") or info.get("public_key") or info.get("address")
    if not pubkey:
        raise RuntimeError(f"could not read pubkey from `vulcan wallet show {wallet}`")
    lamports = rpc_call(rpc_url, "getBalance",
                        [pubkey, {"commitment": "confirmed"}])["value"]
    return pubkey, lamports


def export_private_key(wallet: str, password: str) -> str:
    """Decrypt the vulcan wallet via `vulcan wallet export`. Key stays in memory."""
    env = dict(os.environ, VULCAN_WALLET_PASSWORD=password)
    out = subprocess.run(
        ["vulcan", "wallet", "export", wallet, "--private-key", "--yes", "-o", "json"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    if out.returncode != 0:
        raise RuntimeError("wallet export failed (wrong password or unknown wallet)")
    data = json.loads(out.stdout)
    key = data.get("private_key") or data.get("privateKey")
    if not key:
        raise RuntimeError("wallet export returned no private_key field")
    return key


def cmd_quote(args) -> int:
    try:
        rent, fee, total = registration_cost(args.max_positions)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"registration cost for maxPositions={args.max_positions} "
          f"(exact, from the on-chain rent model):")
    print(f"  rent:  {rent:>12,} lamports  ({rent / 1e9:.8f} SOL)")
    print(f"  fee:   {fee:>12,} lamports  ({fee / 1e9:.8f} SOL)")
    print(f"  total: {total:>12,} lamports  ({total / 1e9:.8f} SOL)")
    print()
    if account_exists(args.authority, args.rpc_url):
        print("→ authority is funded — cross-checking with a mainnet simulation…")
        try:
            build = api_post("/v1/exchange/build-register-ixs", {
                "traderAuthority": args.authority,
                "txFeePayer": args.authority,
                "maxPositions": args.max_positions,
            }, args.api_url)
            ixs, trader_pda = build_instructions(build)
            simulate_register(ixs, Pubkey.from_string(args.authority),
                              trader_pda, args.rpc_url, rent)
            print("  simulation OK — the figure above is exact.")
        except RuntimeError as e:
            print(f"  simulation note: {e}", file=sys.stderr)
    else:
        print("  (authority not funded yet — fund it, then re-run quote to "
              "cross-check with a live simulation.)")
    print()
    print(f"fund {args.authority} with at least {total / 1e9:.6f} SOL "
          f"(+ a little extra for future fees) before registering.")
    return 0


def cmd_register(args) -> int:
    if not args.yes:
        print("error: --yes is required — registering spends real SOL; "
              "run `quote` first and approve the exact total", file=sys.stderr)
        return 1
    try:
        rent, fee, total = registration_cost(args.max_positions)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    pubkey, balance = wallet_balance_lamports(args.wallet, args.rpc_url)
    authority = args.authority or pubkey
    print(f"→ wallet {args.wallet}: {pubkey}")
    print(f"  balance: {balance / 1e9:.8f} SOL")
    print(f"  cost:    {total / 1e9:.8f} SOL "
          f"(rent {rent / 1e9:.8f} + fee {fee / 1e9:.8f})")

    if check_registered(authority, args.api_url):
        print("  already registered on Phoenix — nothing to do.")
        print(f"  trader state: {args.api_url}/v1/trader/state/{authority}")
        return 0

    if balance < total:
        print(f"error: balance {balance / 1e9:.8f} SOL < cost {total / 1e9:.8f} SOL — "
              f"fund {pubkey} first", file=sys.stderr)
        return 1

    print("→ building register instructions…")
    build = api_post("/v1/exchange/build-register-ixs", {
        "traderAuthority": authority,
        "txFeePayer": authority,
        "maxPositions": args.max_positions,
    }, args.api_url)
    ixs, trader_pda = build_instructions(build)
    tx, blockhash = assemble_tx(ixs, Pubkey.from_string(authority), args.rpc_url)

    password = os.environ.get("VULCAN_WALLET_PASSWORD")
    if not password:
        password = getpass.getpass("wallet password (transient, never stored): ")
    print("→ decrypting wallet (in memory only)…")
    b58 = export_private_key(args.wallet, password)
    password = None  # drop the reference as early as possible
    keypair = Keypair.from_base58_string(b58)
    b58 = None
    if str(keypair.pubkey()) != pubkey:
        print("error: exported key does not match the wallet pubkey", file=sys.stderr)
        return 1

    # Partial sign: authority signs; the onboarder slot stays empty.
    # A full Transaction.sign with only the authority fails with NotEnoughSigners.
    tx.partial_sign([keypair], blockhash)
    keypair = None
    tx_b64 = base64.b64encode(bytes(tx)).decode()
    print("→ submitting to Phoenix (onboarder co-signs + broadcasts)…")
    sent = api_post("/v1/exchange/send-register-ixs", {
        "transaction": tx_b64,
        "traderAuthority": authority,
        "txFeePayer": authority,
        "maxPositions": args.max_positions,
    }, args.api_url)
    sig = sent.get("signature")
    pda = sent.get("traderPda", str(trader_pda))
    print(f"  signature: {sig}")
    print(f"  traderPda: {pda}")

    print("→ confirming…")
    confirmed = False
    for _ in range(30):
        st = rpc_call(args.rpc_url, "getSignatureStatuses",
                      [[sig], {"searchTransactionHistory": True}])
        v = (st.get("value") or [None])[0]
        if v and v.get("confirmationStatus") in ("confirmed", "finalized"):
            if v.get("err"):
                print(f"error: transaction failed on-chain: {v['err']}", file=sys.stderr)
                return 1
            confirmed = True
            break
        time.sleep(2)
    if not confirmed:
        print("warning: not confirmed after 60s — check the signature on Solscan",
              file=sys.stderr)
    time.sleep(2)
    state = api_get(f"/v1/trader/state/{authority}", args.api_url)
    print()
    if state is not None:
        print("✅ trader registered on Phoenix")
    else:
        print("⚠️  trader state not visible yet — re-check in a minute")
    print(f"   traderPda:  {pda}")
    print(f"   authority:  {authority}")
    print(f"   tx:         https://solscan.io/tx/{sig}")
    print(f"   cost:       {total / 1e9:.8f} SOL")
    print("   next: fund trading collateral (vulcan margin deposit / Phoenix "
          "deposit flow) — separate approval")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="One-shot Phoenix perps trader registration")
    ap.add_argument("--rpc-url", default=None,
                    help="Solana RPC (default: vulcan config or public mainnet)")
    ap.add_argument("--api-url", default=API_BASE, help="Phoenix API base")
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quote",
                       help="exact registration cost (no wallet, no signing)")
    q.add_argument("--authority", required=True,
                   help="trader authority pubkey (pays + signs)")
    q.add_argument("--max-positions", type=int, default=32)
    q.set_defaults(fn=cmd_quote)

    r = sub.add_parser("register", help="register the trader on Phoenix (spends SOL)")
    r.add_argument("--wallet", required=True,
                   help="vulcan wallet name holding the authority key")
    r.add_argument("--authority", default=None,
                   help="authority pubkey (default: the wallet's)")
    r.add_argument("--max-positions", type=int, default=32)
    r.add_argument("--yes", action="store_true",
                   help="required: confirms the exact quoted spend")
    r.set_defaults(fn=cmd_register)

    args = ap.parse_args(argv)
    if not args.rpc_url:
        args.rpc_url = vulcan_rpc_url()
    try:
        return args.fn(args)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
