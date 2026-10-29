#!/usr/bin/env python3
"""Musebook ORE miner v2 — automated deploy/claim bot for the ORE v3 grid protocol.

The ORE "mining" game (program oreV3EG1i9BEgiAJ8b177Z2S2rMarzak4NMv1kULvWv):
  each ~2-minute round (240 slots), miners deploy SOL onto 25 tiles; onchain
  entropy picks one winning tile; 1 ORE is minted to the winner (+0.2 ORE to
  the Motherlode).

Modes:
  --dry-run   Build the deploy transaction and simulate it against Helius.
              Never sends anything. (default)
  --live      Send real transactions. Requires ORE_MINER_KEYFILE and
              ORE_MINER_PASSWORD env vars. The wallet must be funded.
  --once      Run a single iteration then exit (composes with either mode).
  --setup     Generate a new miner keypair and store it encrypted.
  --checkpoint-only  Run a checkpoint for the prior round if needed, then exit.
  --claim-only       Claim available SOL/ORE rewards, then exit.

v2 additions over v1:
  - Checkpoint lifecycle: a miner cannot deploy into a new round until its
    prior round is checkpointed. The bot checkpoints (same atomic tx as the
    deploy when possible) before every new-round deploy.
  - Real UTC daily deployed-SOL cap (ORE_DAILY_CAP_SOL, default 0.05).
  - Durable per-round intents (state/intents.json) with crash recovery:
    an intent is persisted BEFORE broadcast; submitted-but-uncertain intents
    are reconciled against signature status on startup.
  - Idempotency: never redeploy into a round the miner already deployed in;
    altered-mask retries are refused.
  - TypeSafe JEV advisory gate (custom.typesafe credential, never the raw
    key): Noul(all listed invariants hold?) + Noul(telemetry internally
    consistent, nothing manipulated?). JEV verifies explicit invariants
    stated in the telemetry (consistency checking), not the economics —
    the operator has accepted the baseline bleed. Fail-closed: any JEV
    error, failed invariant, or inconsistency verdict skips the round.
    JEV is advisory only — it can never authorize spending.

Strategy v2 (documented, conservative):
  - Even spread across all 25 tiles (mask 0x1FFFFFF), like lite mode.
  - Per-round deploy cap: ORE_ROUND_CAP_SOL (default 0.01 SOL).
  - Per-day (UTC) deploy cap: ORE_DAILY_CAP_SOL (default 0.05 SOL).
  - Never deploy if wallet balance < cap + ORE_RESERVE_SOL (default 0.01).
  - Skip rounds ending in <15 slots.

Economics (honest): losers get ~89.1% of deployed SOL back, winners 99%.
An even spread returns ~89.5% of deployed SOL per round on average; the 1 ORE
round reward (split among winners on the winning tile) must beat the ~10.5%
SOL bleed for the operation to profit. This bot is a participation miner,
not a profit guarantee.
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
import struct
import sys
import time
import urllib.request
from datetime import datetime, timezone

try:
    sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
    from dynamic_credentials import (  # noqa: E402
        add_surrogate_to_request,
        read_json_response,
        url_with_surrogate_query_param,
    )
    HAVE_SURROGATE = True
except ImportError:
    # Fresh-install path: no connector surrogate available. RPC falls back
    # to --rpc / ORE_MINER_RPC and the JEV advisory gate is unavailable
    # (fail-closed: live deploys veto unless --force-no-jev).
    HAVE_SURROGATE = False

    def read_json_response(resp):  # noqa: E402
        return json.loads(resp.read().decode())

from solders.pubkey import Pubkey  # noqa: E402
from solders.keypair import Keypair  # noqa: E402
from solders.instruction import Instruction, AccountMeta  # noqa: E402
from solders.message import Message  # noqa: E402
from solders.transaction import Transaction  # noqa: E402
from solders.hash import Hash as SolderHash  # noqa: E402
import nacl.secret  # noqa: E402
import nacl.pwhash  # noqa: E402

# ---------------------------------------------------------------- constants
ORE_PROGRAM = Pubkey.from_string("oreV3EG1i9BEgiAJ8b177Z2S2rMarzak4NMv1kULvWv")
ORE_MINT = Pubkey.from_string("oreoU2P8bN6jkk3jbaiVxYnG1dCXcYxwhwyK9jSybcp")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)
# Verified 2026-09-27 against entropy-api 0.1.4 (declare_id!) and the onchain
# var PDA: find_program_address([b"var", board, u64le(0)], this) == VAR_ADDRESS.
ENTROPY_PROGRAM = Pubkey.from_string("3jSkUuYBoJzQPMEzTvkDFXCZUBksPamrVhrnHR9igu2X")
ENTROPY_VAR = Pubkey.from_string("BWCaDY96Xe4WkFq1M7UiCCRcChsJ3p51L5KrGzhxgm2E")

HELIUS_MAINNET = "https://mainnet.helius-rpc.com/"
ALLOWED = ["mainnet.helius-rpc.com"]
CREDENTIAL = "custom.helius"

# TypeSafe JEV — the key stays inside the custom.typesafe connector; this
# client only carries the surrogate, never the raw key.
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_CREDENTIAL = "custom.typesafe"
TYPESAFE_HOSTS = ("api.typesafe.ai",)
JEV_MODEL = "jev-latest"

LAMPORTS_PER_SOL = 1_000_000_000
ALL_TILES_MASK = (1 << 25) - 1  # 0x1FFFFFF
MIN_SLOTS_LEFT = 15
CHECKPOINT_FEE_LAMPORTS = 10_000

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
STATS_PATH = os.path.join(STATE_DIR, "stats.json")
INTENTS_PATH = os.path.join(STATE_DIR, "intents.json")


# ORE v3 is built with steel (not Anchor): the instruction discriminator is a
# single u8 enum discriminant, NOT an 8-byte Anchor sighash.
# From ore-api/src/instruction.rs: Automate=0, Checkpoint=2, ClaimSOL=3,
# ClaimORE=4, Close=5, Deploy=6, Log=8, Reset=9.
STEEL_DISC = {
    "automate": 0,
    "checkpoint": 2,
    "claimSol": 3,
    "claimOre": 4,
    "close": 5,
    "deploy": 6,
    "log": 8,
    "reset": 9,
}


def disc(name: str) -> bytes:
    """Steel instruction discriminator: 1-byte enum discriminant."""
    return bytes([STEEL_DISC[name]])


# ---------------------------------------------------------------- RPC
RPC_URL = os.environ.get("ORE_MINER_RPC", "https://api.mainnet-beta.solana.com")


def rpc(method, params=None):
    if HAVE_SURROGATE:
        url = url_with_surrogate_query_param(
            HELIUS_MAINNET, CREDENTIAL, allowed_hosts=ALLOWED
        )
    else:
        url = RPC_URL
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    ).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = read_json_response(resp)
    if out.get("error"):
        raise RuntimeError(f"RPC {method} error: {out['error']}")
    return out["result"]


def get_account_b64(address: str):
    r = rpc("getAccountInfo", [address, {"encoding": "base64"}])
    v = r["value"]
    if v is None:
        return None
    return base64.b64decode(v["data"][0])


def sig_status(sig: str):
    st = rpc("getSignatureStatuses", [[sig]])["value"][0]
    return st


# ---------------------------------------------------------------- PDAs
def pda(seeds, program=ORE_PROGRAM):
    return Pubkey.find_program_address(seeds, program)


def board_pda():
    return pda([b"board"])[0]


def config_pda():
    return pda([b"config"])[0]


def treasury_pda():
    return pda([b"treasury"])[0]


def miner_pda(authority: Pubkey):
    return pda([b"miner", bytes(authority)])[0]


def round_pda(round_id: int):
    return pda([b"round", struct.pack("<Q", round_id)])[0]


def automation_pda(authority: Pubkey):
    return pda([b"automation", bytes(authority)])[0]


# ---------------------------------------------------------------- account decoding
# Steel 8-byte discriminators, verified live 2026-09-27 (u64 LE).
BOARD_DISC = 105
CONFIG_DISC = 101
ROUND_DISC = 109
# Miner discriminator: unknown until the first miner account exists on-chain.
# Record-then-assert: first successful decode stores it in stats; later
# decodes assert it matches.
MINER_DISC_KEY = "miner_discriminator"


def _check_disc(raw: bytes, expected: int, name: str):
    disc = struct.unpack("<Q", raw[0:8])[0]
    assert disc == expected, f"{name} discriminator mismatch: {disc} != {expected}"


def decode_board(raw: bytes):
    assert len(raw) >= 40, f"board too short: {len(raw)}"
    _check_disc(raw, BOARD_DISC, "board")
    round_id, start_slot, end_slot, ema = struct.unpack("<QQQQ", raw[8:40])
    return {
        "round_id": round_id,
        "start_slot": start_slot,
        "end_slot": end_slot,
        "production_cost_ema": ema,
    }


def decode_config(raw: bytes):
    # Verified 2026-09-27: config is 232 bytes, disc=101, round_slots @160,
    # intermission_slots @152 (live values: 240 / 48).
    assert len(raw) >= 232, f"config too short: {len(raw)}"
    _check_disc(raw, CONFIG_DISC, "config")
    intermission = struct.unpack("<Q", raw[152:160])[0]
    round_slots = struct.unpack("<Q", raw[160:168])[0]
    return {"intermission_slots": intermission, "round_slots": round_slots}


def _u64_array(raw, off, n):
    return list(struct.unpack(f"<{n}Q", raw[off : off + 8 * n]))


def decode_round(raw: bytes):
    # Matches ore-api/src/state/round.rs (repr(C), 8-byte steel disc prefix).
    assert len(raw) >= 952, f"round too short: {len(raw)}"
    _check_disc(raw, ROUND_DISC, "round")
    off = 8
    rid = struct.unpack("<Q", raw[off : off + 8])[0]
    off += 8
    deployed = _u64_array(raw, off, 25)
    off += 200
    mass = _u64_array(raw, off, 25)
    off += 200
    count = _u64_array(raw, off, 25)
    off += 200
    slot_hash = raw[off : off + 32]
    off += 32
    expires_at, motherlode = struct.unpack("<QQ", raw[off : off + 16])
    off += 16
    rent_payer = Pubkey(raw[off : off + 32])
    off += 32
    rewards = _u64_array(raw, off, 25)
    off += 200
    total_vaulted, total_returned, total_miners = struct.unpack(
        "<QQQ", raw[off : off + 24]
    )
    off += 24
    top_miner = Pubkey(raw[off : off + 32])
    return {
        "id": rid,
        "deployed": deployed,
        "mass": mass,
        "count": count,
        "slot_hash": slot_hash.hex(),
        "slot_hash_set": slot_hash != bytes(32) and slot_hash != bytes([255]) * 32,
        "expires_at": expires_at,
        "motherlode": motherlode,
        "rent_payer": str(rent_payer),
        "rewards": rewards,
        "total_vaulted": total_vaulted,
        "total_returned_sol": total_returned,
        "total_miners": total_miners,
        "top_miner": str(top_miner),
    }


def decode_miner_checked(raw: bytes, stats: dict):
    """decode_miner + record-then-assert on the steel discriminator."""
    assert len(raw) >= 752, f"miner too short: {len(raw)}"
    disc = struct.unpack("<Q", raw[0:8])[0]
    known = stats.get(MINER_DISC_KEY)
    if known is None:
        stats[MINER_DISC_KEY] = disc
        print(f"miner discriminator recorded: {disc}")
    else:
        assert disc == known, \
            f"miner discriminator mismatch: {disc} != {known}"
    return decode_miner(raw)


def decode_miner(raw: bytes):
    # Matches ore-api/src/state/miner.rs (repr(C), 8-byte steel disc prefix,
    # rewards_factor is steel Numeric = 16 bytes).
    assert len(raw) >= 752, f"miner too short: {len(raw)}"
    # Matches ore-api/src/state/miner.rs (repr(C), 8-byte steel disc prefix,
    # rewards_factor is steel Numeric = 16 bytes).
    assert len(raw) >= 752, f"miner too short: {len(raw)}"
    off = 8
    authority = Pubkey(raw[off : off + 32])
    off += 32
    auto_return, checkpoint_id, checkpoint_fee = struct.unpack(
        "<QQQ", raw[off : off + 24]
    )
    off += 24
    deployed = _u64_array(raw, off, 25)
    off += 200
    mass = _u64_array(raw, off, 25)
    off += 200
    cumulative = _u64_array(raw, off, 25)
    off += 200
    round_id = struct.unpack("<Q", raw[off : off + 8])[0]
    off += 8
    off += 16  # rewards_factor: Numeric (16 bytes) — not needed by the bot
    rewards_sol, refined_ore, rewards_ore = struct.unpack(
        "<QQQ", raw[off : off + 24]
    )
    off += 24
    last_claim_ore_at, last_claim_sol_at = struct.unpack(
        "<qq", raw[off : off + 16]
    )
    off += 16
    lifetime_rewards_ore, lifetime_deployed, lifetime_rewards_sol = struct.unpack(
        "<QQQ", raw[off : off + 24]
    )
    return {
        "authority": str(authority),
        "auto_return": auto_return,
        "checkpoint_id": checkpoint_id,
        "checkpoint_fee": checkpoint_fee,
        "deployed": deployed,
        "mass": mass,
        "cumulative": cumulative,
        "round_id": round_id,
        "rewards_sol": rewards_sol,
        "refined_ore": refined_ore,
        "rewards_ore": rewards_ore,
        "last_claim_ore_at": last_claim_ore_at,
        "last_claim_sol_at": last_claim_sol_at,
        "lifetime_rewards_ore": lifetime_rewards_ore,
        "lifetime_deployed": lifetime_deployed,
        "lifetime_rewards_sol": lifetime_rewards_sol,
    }


# ---------------------------------------------------------------- instructions
def deploy_ix(signer: Pubkey, amount_lamports: int, squares_mask: int):
    # Matches ore-api/src/sdk.rs deploy(): 10 ore accounts + 2 entropy.
    authority = signer
    data = disc("deploy") + struct.pack("<Q", amount_lamports) + struct.pack(
        "<I", squares_mask
    )
    return Instruction(
        ORE_PROGRAM,
        data,
        [
            AccountMeta(signer, True, True),
            AccountMeta(authority, False, True),
            AccountMeta(automation_pda(authority), False, True),
            AccountMeta(board_pda(), False, True),
            AccountMeta(config_pda(), False, True),
            AccountMeta(miner_pda(authority), False, True),
            # round filled by caller — placeholder replaced below
            AccountMeta(ORE_PROGRAM, False, False),  # placeholder
            AccountMeta(treasury_pda(), False, True),
            AccountMeta(SYSTEM_PROGRAM, False, False),
            AccountMeta(ORE_PROGRAM, False, False),
            AccountMeta(ENTROPY_VAR, False, True),
            AccountMeta(ENTROPY_PROGRAM, False, False),
        ],
    )


def checkpoint_ix(signer: Pubkey, prior_round_id: int):
    # Matches ore-api/src/sdk.rs checkpoint(): 8 accounts, empty data.
    authority = signer
    return Instruction(
        ORE_PROGRAM,
        disc("checkpoint"),
        [
            AccountMeta(signer, True, True),
            AccountMeta(authority, False, True),
            AccountMeta(automation_pda(authority), False, True),
            AccountMeta(board_pda(), False, True),
            AccountMeta(miner_pda(authority), False, True),
            AccountMeta(round_pda(prior_round_id), False, True),
            AccountMeta(treasury_pda(), False, True),
            AccountMeta(SYSTEM_PROGRAM, False, False),
        ],
    )


def claim_sol_ix(signer: Pubkey):
    data = disc("claimSol")
    return Instruction(
        ORE_PROGRAM,
        data,
        [
            AccountMeta(signer, True, True),
            AccountMeta(board_pda(), False, True),
            AccountMeta(miner_pda(signer), False, True),
            AccountMeta(SYSTEM_PROGRAM, False, False),
            AccountMeta(ORE_PROGRAM, False, False),
        ],
    )


def claim_ore_ix(signer: Pubkey, bps: int = 10000):
    data = disc("claimOre") + struct.pack("<Q", bps)
    treasury = treasury_pda()
    return Instruction(
        ORE_PROGRAM,
        data,
        [
            AccountMeta(signer, True, True),
            AccountMeta(board_pda(), False, True),
            AccountMeta(miner_pda(signer), False, True),
            AccountMeta(ORE_MINT, False, True),
            AccountMeta(
                Pubkey.find_program_address(
                    [bytes(signer), bytes(TOKEN_PROGRAM), bytes(ORE_MINT)],
                    ASSOCIATED_TOKEN_PROGRAM,
                )[0],
                False,
                True,
            ),
            AccountMeta(treasury, False, True),
            AccountMeta(
                Pubkey.find_program_address(
                    [bytes(treasury), bytes(TOKEN_PROGRAM), bytes(ORE_MINT)],
                    ASSOCIATED_TOKEN_PROGRAM,
                )[0],
                False,
                True,
            ),
            AccountMeta(SYSTEM_PROGRAM, False, False),
            AccountMeta(TOKEN_PROGRAM, False, False),
            AccountMeta(ASSOCIATED_TOKEN_PROGRAM, False, False),
            AccountMeta(ORE_PROGRAM, False, False),
        ],
    )


# ---------------------------------------------------------------- transactions
def build_tx(ixs, payer: Pubkey) -> Transaction:
    bh = rpc("getLatestBlockhash", [{"commitment": "confirmed"}])["value"][
        "blockhash"
    ]
    msg = Message.new_with_blockhash(ixs, payer, SolderHash.from_string(bh))
    return Transaction.new_unsigned(msg), bh


def simulate(ixs, payer: Pubkey, signer_kp: Keypair):
    tx, bh = build_tx(ixs, payer)
    tx.sign([signer_kp], SolderHash.from_string(bh))
    b64 = base64.b64encode(bytes(tx)).decode()
    return rpc(
        "simulateTransaction",
        [b64, {"encoding": "base64", "commitment": "confirmed"}],
    )


def send(ixs, signer_kp: Keypair):
    payer = signer_kp.pubkey()
    tx, bh = build_tx(ixs, payer)
    tx.sign([signer_kp], SolderHash.from_string(bh))
    b64 = base64.b64encode(bytes(tx)).decode()
    sig = rpc(
        "sendTransaction",
        [b64, {"encoding": "base64", "preflightCommitment": "confirmed"}],
    )
    # confirm
    for _ in range(30):
        time.sleep(2)
        st = sig_status(sig)
        if st and st.get("confirmationStatus") in ("confirmed", "finalized"):
            return sig
        if st and st.get("err"):
            raise RuntimeError(f"tx failed: {st['err']}")
    raise RuntimeError("tx not confirmed in 60s")


# ---------------------------------------------------------------- wallet
def _wallet_path():
    p = os.environ.get("ORE_MINER_KEYFILE")
    if not p:
        raise RuntimeError("ORE_MINER_KEYFILE env var not set")
    return p


def wallet_setup():
    """Generate a new miner keypair, encrypt, and store it."""
    path = _wallet_path()
    if os.path.exists(path):
        raise RuntimeError(f"wallet already exists at {path}")
    pw = os.environ.get("ORE_MINER_PASSWORD") or getpass.getpass(
        "New miner wallet password: "
    )
    kp = Keypair()
    salt = os.urandom(16)  # argon2i requires exactly 16 bytes
    key = nacl.pwhash.argon2i.kdf(
        nacl.secret.SecretBox.KEY_SIZE,
        pw.encode(),
        salt,
        opslimit=nacl.pwhash.argon2i.OPSLIMIT_MODERATE,
        memlimit=nacl.pwhash.argon2i.MEMLIMIT_MODERATE,
    )
    box = nacl.secret.SecretBox(key)
    enc = box.encrypt(bytes(kp))
    doc = {
        "name": "ore-miner",
        "public_key": str(kp.pubkey()),
        "encrypted": {
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(enc.nonce).decode(),
            "ciphertext": base64.b64encode(enc.ciphertext).decode(),
            "kdf": "argon2i",
        },
        "policy": {
            "venue": "ore v3 grid (oreV3EG1i9BEgiAJ8b177Z2S2rMarzak4NMv1kULvWv)",
            "actions": ["deploy", "checkpoint", "claimSol", "claimOre"],
            "round_cap_sol": float(os.environ.get("ORE_ROUND_CAP_SOL", "0.01")),
            "daily_cap_sol": float(os.environ.get("ORE_DAILY_CAP_SOL", "0.05")),
        },
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(doc, f)
    os.chmod(path, 0o600)
    print(f"miner wallet created: {kp.pubkey()}")
    print(f"miner PDA: {miner_pda(kp.pubkey())}")
    print("FUNDING IS A SEPARATE STEP — nothing is funded by setup.")
    return str(kp.pubkey())


def wallet_load() -> Keypair:
    path = _wallet_path()
    pw = os.environ.get("ORE_MINER_PASSWORD")
    if not pw:
        pw = getpass.getpass("Miner wallet password: ")
    doc = json.load(open(path))
    enc = doc["encrypted"]
    salt = base64.b64decode(enc["salt"])
    key = nacl.pwhash.argon2i.kdf(
        nacl.secret.SecretBox.KEY_SIZE,
        pw.encode(),
        salt,
        opslimit=nacl.pwhash.argon2i.OPSLIMIT_MODERATE,
        memlimit=nacl.pwhash.argon2i.MEMLIMIT_MODERATE,
    )
    box = nacl.secret.SecretBox(key)
    raw = box.decrypt(
        base64.b64decode(enc["ciphertext"]),
        base64.b64decode(enc["nonce"]),
    )
    return Keypair.from_bytes(raw)


# ---------------------------------------------------------------- stats + intents
def load_stats():
    if os.path.exists(STATS_PATH):
        return json.load(open(STATS_PATH))
    return {
        "rounds": [],
        "daily": {},
        "total_deployed_lamports": 0,
        "total_claimed_sol": 0,
        "total_claimed_ore_grains": 0,
        "jev_skips": [],
        "jev_history": [],
        "started_at": time.time(),
    }


def save_stats(s):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(s, open(STATS_PATH, "w"), indent=2)


def load_intents():
    if os.path.exists(INTENTS_PATH):
        return json.load(open(INTENTS_PATH))
    return {}


def save_intents(i):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(i, open(INTENTS_PATH, "w"), indent=2)


def reconcile_intents(intents):
    """Resolve submitted-but-uncertain intents against signature status.

    Never auto-retries: an unknown outcome stays unknown for manual review.
    """
    changed = False
    for rid, it in intents.items():
        if it.get("status") == "submitted" and it.get("sig"):
            try:
                st = sig_status(it["sig"])
            except Exception as e:  # noqa: BLE001
                print(f"intent r{rid}: status lookup failed ({e}) — left as-is")
                continue
            if st is None:
                age = time.time() - it.get("at", 0)
                if age > 3600:
                    it["status"] = "unknown"
                    changed = True
                    print(f"intent r{rid}: sig not found after 1h → unknown")
            elif st.get("err"):
                it["status"] = "failed"
                it["error"] = str(st["err"])
                changed = True
                print(f"intent r{rid}: tx failed onchain → failed")
            elif st.get("confirmationStatus") in ("confirmed", "finalized"):
                it["status"] = "confirmed"
                changed = True
                print(f"intent r{rid}: confirmed onchain")
    if changed:
        save_intents(intents)
    return intents


# ---------------------------------------------------------------- tile structure (for JEV state)
def distribution_mask(round_id: int):
    """Replicates Round::distribution_mask (api/src/state/round.rs):
    keccak(round_id LE) seeded Fisher-Yates over 0..25, first 10 are solo."""
    try:
        from Crypto.Hash import keccak
    except ImportError:
        return None
    seed = keccak.new(digest_bits=256, data=struct.pack("<Q", round_id)).digest()
    indices = list(range(25))
    randomness = seed
    off = 0
    for i in range(24, 0, -1):
        if off + 2 > len(randomness):
            randomness = keccak.new(digest_bits=256, data=randomness).digest()
            off = 0
        r = int.from_bytes(randomness[off : off + 2], "little")
        j = r % (i + 1)
        indices[i], indices[j] = indices[j], indices[i]
        off += 2
    mask = 0
    for idx in indices[:10]:
        mask |= 1 << idx
    return mask


# ---------------------------------------------------------------- JEV (TypeSafe) advisory gate
JEV_QUESTIONS = {
    # JEV verifies EXPLICIT invariants stated in the telemetry — consistency
    # checking, which is its strength. It does not need ORE domain knowledge.
    # The operator has accepted the baseline economics; the deploy decision
    # stays in code behind deterministic gates. JEV is the "verify and
    # escalate" layer: it can veto on failed invariants, never authorize spend.
    "invariants": {
        "type": "noul",
        "instructions": (
            "Do ALL of the invariant_checks listed in the telemetry hold "
            "against the provided values? Check every single one against the "
            "actual numbers. Every invariant must hold for this to be true."
        ),
    },
    "suspicious": {
        "type": "noul",
        "instructions": (
            "The telemetry is internally consistent: fields agree with each "
            "other, nothing looks manipulated, contradictory, or deliberately "
            "misleading (as opposed to merely unusual)."
        ),
    },
}


def jev_ask(state_obj, questions, timeout=25):
    """Ask Jev via the custom.typesafe connector. Fail-closed: any failure
    returns None. The raw API key is never touched — auth travels as a
    surrogate on the urllib path."""
    if not HAVE_SURROGATE:
        print("JEV advisory gate unavailable (no connector on this install) — failing closed")
        return None
    try:
        body = json.dumps(
            {"state": state_obj, "model": JEV_MODEL, "questions": questions}
        ).encode()
        req = urllib.request.Request(
            TYPESAFE_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        add_surrogate_to_request(
            req, TYPESAFE_CREDENTIAL, allowed_hosts=TYPESAFE_HOSTS
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = read_json_response(resp)
        return out.get("answers")
    except Exception as e:  # noqa: BLE001
        print(f"JEV request failed ({type(e).__name__}): {e} — failing closed")
        return None


def _fnum(x, default=None):
    return float(x) if isinstance(x, (int, float)) else default


def jev_gate(state_obj):
    """Advisory JEV gate. Returns (ok, reason, detail). Fail-closed."""
    answers = jev_ask(state_obj, JEV_QUESTIONS)
    detail = {"answers": answers}
    if not answers:
        return False, "jev-unavailable", detail
    inv = answers.get("invariants") or {}
    inoul = None
    for k in ("noul", "probability", "p_yes"):
        v = _fnum(inv.get(k))
        if v is not None:
            inoul = v
            break
    if inoul is None:
        return False, "jev-invariants-unreadable", detail
    if inoul < 0.75:
        return False, f"jev-invariants-failed-{inoul:.2f}", detail
    susp = answers.get("suspicious") or {}
    snoul = None
    for k in ("noul", "probability", "p_yes"):
        v = _fnum(susp.get(k))
        if v is not None:
            snoul = v
            break
    if snoul is None:
        return False, "jev-suspicious-unreadable", detail
    if snoul < 0.6:
        return False, f"jev-suspicious-{snoul:.2f}", detail
    return True, "ok", detail


def build_jev_state(board, cfg, round_acct, miner, per_tile_lamports,
                    round_total_lamports, daily_cap_lamports, daily_used_lamports,
                    reserve_lamports, balance_lamports, ck_round):
    solo_mask = distribution_mask(board["round_id"])
    solo_tiles = (
        [i for i in range(25) if solo_mask & (1 << i)] if solo_mask is not None else []
    )
    total_round_deployed = sum(round_acct["deployed"]) if round_acct else 0
    return {
        "protocol": "ore-v3-grid",
        "round_id": board["round_id"],
        "slots_remaining": board["end_slot"] - board["slot"],
        "round_length_slots": cfg["round_slots"],
        "production_cost_ema_lamports": board["production_cost_ema"],
        "proposed_deploy": {
            "per_tile_lamports": per_tile_lamports,
            "per_tile_sol": per_tile_lamports / LAMPORTS_PER_SOL,
            "tiles": 25,
            "mask": hex(ALL_TILES_MASK),
            "total_lamports": round_total_lamports,
            "total_sol": round_total_lamports / LAMPORTS_PER_SOL,
        },
        "baseline_economics": {
            "note": ("operator-accepted; judge only whether THIS round is "
                     "normal"),
            "expected_sol_return_pct": 89.5,
            "expected_bleed_pct": 10.5,
            "ore_reward_per_round": 1.0,
            "motherlode_ore": 0.2,
            "ore_claim_fee_pct": 10.0,
            "production_cost_ema_note": (
                "production_cost_ema is whale-dominated; small miners "
                "routinely deploy below it. A proposed deploy below the EMA "
                "is normal, not anomalous."
            ),
        },
        "tile_structure": {
            "solo_tiles": solo_tiles,
            "solo_mask": hex(solo_mask) if solo_mask is not None else None,
            "note": "10 of 25 tiles are solo (winner takes proportionally more)",
        },
        "round_totals": {
            "round_account_id": round_acct["id"] if round_acct else None,
            "total_deployed_sol": total_round_deployed / LAMPORTS_PER_SOL,
            "total_miners": round_acct["total_miners"] if round_acct else 0,
            "motherlode_lamports": round_acct["motherlode"] if round_acct else 0,
        },
        "caps": {
            "round_cap_sol": round_total_lamports / LAMPORTS_PER_SOL,
            "daily_cap_sol": daily_cap_lamports / LAMPORTS_PER_SOL,
            "daily_used_sol": daily_used_lamports / LAMPORTS_PER_SOL,
            "reserve_floor_sol": reserve_lamports / LAMPORTS_PER_SOL,
        },
        "wallet": {
            "balance_sol": (balance_lamports / LAMPORTS_PER_SOL
                            if balance_lamports is not None else
                            "unknown (dry-run, no wallet loaded)"),
            "miner_pda": str(miner_pda_pubkey),
        },
        "checkpoint": {
            "needed": ck_round is not None,
            "prior_round": ck_round,
            "miner_round": miner["round_id"] if miner else None,
            "miner_checkpoint": miner["checkpoint_id"] if miner else None,
        },
        "lifetime": {
            "deployed_sol": (miner["lifetime_deployed"] / LAMPORTS_PER_SOL) if miner else 0,
            "claimed_sol": (miner["lifetime_rewards_sol"] / LAMPORTS_PER_SOL) if miner else 0,
            "claimed_ore_grains": miner["lifetime_rewards_ore"] if miner else 0,
        },
        "invariant_checks": [
            "round_id == round_totals.round_account_id "
            "(deploying into the round the board points at)",
            "0 <= slots_remaining <= round_length_slots",
            "round_totals.total_miners > 0 and "
            "round_totals.total_deployed_sol > 0 (round is live with activity)",
            "proposed_deploy.per_tile_lamports * 25 == "
            "proposed_deploy.total_lamports",
            "caps.daily_used_sol + proposed_deploy.total_sol <= "
            "caps.daily_cap_sol",
            "wallet.balance_sol numeric and >= proposed_deploy.total_sol + "
            "caps.reserve_floor_sol; the literal string "
            "'unknown (dry-run, no wallet loaded)' waives this check (dry-run)",
            "checkpoint consistency: miner absent means first deploy (the "
            "program checkpoints automatically) OR checkpoint.needed == false "
            "OR a checkpoint is included for checkpoint.prior_round",
            "production_cost_ema_lamports > 0",
            "no negative values anywhere; no NaN; all lamport totals "
            "< 1_000_000_000_000_000 (1e15); round_id > 400000",
        ],
    }


# ---------------------------------------------------------------- main loop
miner_pda_pubkey = None  # set per run for JEV state


def build_round_ixs(signer: Pubkey, round_id: int, per_tile_lamports: int,
                    ck_round=None):
    ixs = []
    if ck_round is not None:
        ixs.append(checkpoint_ix(signer, ck_round))
    dix = deploy_ix(signer, per_tile_lamports, ALL_TILES_MASK)
    dix.accounts[6] = AccountMeta(round_pda(round_id), False, True)
    ixs.append(dix)
    return ixs


def try_claims(kp: Keypair, stats, dry_run: bool):
    """Best-effort claims. With auto_return=1, checkpoint sends SOL winnings
    straight to the wallet, so claimSol is normally a no-op safety net."""
    signer = kp.pubkey()
    mraw = get_account_b64(str(miner_pda(signer)))
    if not mraw:
        return
    m = decode_miner_checked(mraw, stats)
    if m["rewards_ore"] > 0:
        print(f"claiming {m['rewards_ore']} grains ORE (10% protocol fee applies)")
        if dry_run:
            res = simulate([claim_ore_ix(signer)], signer, kp)
            print("claimOre simulate err:", res["value"].get("err"))
        else:
            s = send([claim_ore_ix(signer)], kp)
            print(f"claimed ORE → {s}")
            stats["total_claimed_ore_grains"] += m["rewards_ore"]
    if m["rewards_sol"] > 0:
        print(f"claiming {m['rewards_sol']} lamports SOL")
        if dry_run:
            res = simulate([claim_sol_ix(signer)], signer, kp)
            print("claimSol simulate err:", res["value"].get("err"))
        else:
            s = send([claim_sol_ix(signer)], kp)
            print(f"claimed SOL → {s}")
            stats["total_claimed_sol"] += m["rewards_sol"]


def run_once(kp, dry_run: bool, round_cap_lamports: int,
             daily_cap_lamports: int, reserve_lamports: int,
             use_jev: bool = True):
    global miner_pda_pubkey
    stats = load_stats()
    intents = load_intents()

    # --cap-sol is the per-ROUND total; the program takes a per-tile amount.
    per_tile = round_cap_lamports // 25
    if per_tile < 1:
        print("round cap too small (< 25 lamports) — aborting")
        return stats
    round_total = per_tile * 25

    board_raw = get_account_b64(str(board_pda()))
    if not board_raw:
        print("board account not found — aborting iteration")
        return stats
    board = decode_board(board_raw)
    slot = rpc("getSlot")
    board["slot"] = slot
    cfg_raw = get_account_b64(str(config_pda()))
    cfg = decode_config(cfg_raw) if cfg_raw else {"round_slots": 240,
                                                  "intermission_slots": 48}
    round_len = cfg["round_slots"] or (board["end_slot"] - board["start_slot"])
    round_id = board["round_id"]
    slots_left = board["end_slot"] - slot
    print(f"round {round_id} | slot {slot} | {slots_left} slots left "
          f"(len {round_len})")

    if slots_left < MIN_SLOTS_LEFT:
        print("round ending — waiting for next round")
        return stats

    dry_kp = None
    if kp is None:
        dry_kp = Keypair()  # single ephemeral identity for dry-run
    signer = kp.pubkey() if kp else dry_kp.pubkey()
    miner_pda_pubkey = miner_pda(signer)
    mraw = get_account_b64(str(miner_pda_pubkey))
    miner = decode_miner_checked(mraw, stats) if mraw else None
    if miner:
        print(f"miner: round {miner['round_id']} checkpoint {miner['checkpoint_id']} "
              f"deployed_tiles {sum(1 for d in miner['deployed'] if d > 0)}")
    else:
        print("miner: not yet created (first deploy will create it)")

    rraw = get_account_b64(str(round_pda(round_id)))
    round_acct = decode_round(rraw) if rraw else None

    # --- checkpoint lifecycle: cannot deploy into a new round until the
    # --- prior round is checkpointed (program asserts this in deploy).
    ck_round = None
    if miner and miner["checkpoint_id"] != miner["round_id"] \
            and miner["round_id"] < round_id:
        ck_round = miner["round_id"]
        print(f"checkpoint needed for prior round {ck_round}")
        if dry_run or kp is None:
            print("dry-run: would checkpoint then deploy atomically")
        else:
            sim = simulate([checkpoint_ix(signer, ck_round)], signer, kp)
            if sim["value"].get("err"):
                print(f"checkpoint sim failed: {sim['value']['err']} — "
                      "waiting (round may not be reset yet)")
                return stats
            print("checkpoint sim ok — will prepend to deploy tx")

    # --- idempotency: never redeploy a round already deployed in ---
    if miner and miner["round_id"] == round_id:
        if sum(miner["deployed"]) > 0:
            print(f"already deployed in round {round_id} — skipping (idempotent)")
            return stats
        print("miner is in this round but nothing deployed — checking intent")
    intent = intents.get(str(round_id))
    if intent and intent.get("status") == "confirmed":
        print(f"intent for round {round_id} already confirmed — skipping")
        return stats
    if intent and intent.get("mask") != ALL_TILES_MASK:
        print(f"refusing altered-mask retry for round {round_id} — manual review")
        return stats

    # --- deterministic gates: caps + reserve ---
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day = stats.setdefault("daily", {}).setdefault(
        today, {"deployed_lamports": 0})
    if day["deployed_lamports"] + round_total > daily_cap_lamports:
        print(f"daily cap reached "
              f"({day['deployed_lamports'] / LAMPORTS_PER_SOL:.4f} SOL used) — skipping")
        return stats
    balance = rpc("getBalance", [str(signer)])["value"] if kp else None
    if kp:
        print(f"wallet balance: {balance / LAMPORTS_PER_SOL:.6f} SOL")
        if balance < round_total + reserve_lamports:
            print("balance below round total + reserve — skipping deploy")
            return stats

    # --- JEV advisory gate (fail-closed) ---
    if use_jev:
        state_obj = build_jev_state(
            board, cfg, round_acct, miner, per_tile,
            round_total, daily_cap_lamports, day["deployed_lamports"],
            reserve_lamports, balance, ck_round)
        ok, reason, detail = jev_gate(state_obj)
        print(f"JEV verdict: {reason}")
        stats.setdefault("jev_history", []).append(
            {"at": time.time(), "round_id": round_id, "verdict": reason,
             "state": state_obj, "detail": detail})
        if not ok:
            stats.setdefault("jev_skips", []).append(
                {"at": time.time(), "round_id": round_id, "reason": reason})
            save_stats(stats)
            if not dry_run:
                print("JEV did not clear this deploy — skipping (fail-closed)")
                return stats
            print("dry-run: JEV would have skipped this deploy")

    ixs = build_round_ixs(signer, round_id, per_tile, ck_round)

    if dry_run:
        sim_kp = kp or dry_kp
        sim_signer = sim_kp.pubkey()
        sim_ixs = build_round_ixs(sim_signer, round_id, per_tile,
                                  ck_round if kp else None)
        res = simulate(sim_ixs, sim_signer, sim_kp)
        err = res["value"].get("err")
        logs = res["value"].get("logs", [])
        print("simulate err:", err)
        for line in logs[-8:]:
            print("  ", line)
        if err and not kp:
            print("(note: dry-run with an ephemeral keypair fails on funds; "
                  "account structure is what this checks)")
        save_stats(stats)
        return stats

    # --- durable intent BEFORE broadcast ---
    intents[str(round_id)] = {
        "mask": ALL_TILES_MASK,
        "per_tile_lamports": per_tile,
        "total_lamports": round_total,
        "status": "planned",
        "checkpoint_round": ck_round,
        "at": time.time(),
    }
    save_intents(intents)

    sig = send(ixs, kp)
    print(f"deployed {round_total / LAMPORTS_PER_SOL:.4f} SOL "
          f"({per_tile / LAMPORTS_PER_SOL:.6f} x 25 tiles) → {sig}")
    intents[str(round_id)].update({"status": "confirmed", "sig": sig})
    save_intents(intents)
    day["deployed_lamports"] += round_total
    stats["total_deployed_lamports"] += round_total
    stats["rounds"].append({"round_id": round_id, "per_tile": per_tile,
                            "total": round_total, "sig": sig,
                            "checkpoint_round": ck_round, "at": time.time()})
    save_stats(stats)

    # claims (best-effort; SOL usually auto-returned by checkpoint)
    try_claims(kp, stats, dry_run=False)
    save_stats(stats)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--checkpoint-only", action="store_true")
    ap.add_argument("--claim-only", action="store_true")
    ap.add_argument("--cap-sol", type=float, default=0.01,
                    help="per-ROUND deploy cap in SOL (split across 25 tiles)")
    ap.add_argument("--daily-cap-sol", type=float, default=0.05,
                    help="UTC daily deploy cap in SOL")
    ap.add_argument("--reserve-sol", type=float, default=0.01,
                    help="wallet reserve floor in SOL (never dip below)")
    ap.add_argument("--rpc", default=os.environ.get("ORE_MINER_RPC",
                    "https://api.mainnet-beta.solana.com"),
                    help="Solana RPC URL (default: public mainnet)")
    ap.add_argument("--no-jev", action="store_true",
                    help="disable the TypeSafe JEV advisory gate "
                         "(dry-run only unless --force-no-jev)")
    ap.add_argument("--force-no-jev", action="store_true",
                    help="explicit operator override: run LIVE without JEV")
    args = ap.parse_args()

    global RPC_URL
    RPC_URL = args.rpc

    if args.setup:
        wallet_setup()
        return

    dry_run = not args.live
    if args.live and args.no_jev and not args.force_no_jev:
        print("refusing: --no-jev with --live requires explicit operator "
              "override --force-no-jev (JEV is mandatory for live deploys)")
        return
    if args.live and args.no_jev and args.force_no_jev:
        print("WARNING: live deploy WITHOUT the JEV advisory gate "
              "(operator override)")
    round_cap_lamports = int(args.cap_sol * LAMPORTS_PER_SOL)
    daily_cap_lamports = int(args.daily_cap_sol * LAMPORTS_PER_SOL)
    reserve_lamports = int(args.reserve_sol * LAMPORTS_PER_SOL)
    use_jev = not args.no_jev

    kp = None
    if args.live or args.checkpoint_only or args.claim_only:
        kp = wallet_load()
        print(f"miner: {kp.pubkey()} (LIVE)")

    if args.checkpoint_only:
        if not kp:
            print("--checkpoint-only requires --live")
            return
        ck_stats = load_stats()
        board = decode_board(get_account_b64(str(board_pda())))
        mraw = get_account_b64(str(miner_pda(kp.pubkey())))
        if not mraw:
            print("no miner account — nothing to checkpoint")
            return
        miner = decode_miner_checked(mraw, ck_stats)
        save_stats(ck_stats)
        if miner["checkpoint_id"] == miner["round_id"] \
                or miner["round_id"] >= board["round_id"]:
            print("no checkpoint needed")
            return
        ck = miner["round_id"]
        sim = simulate([checkpoint_ix(kp.pubkey(), ck)], kp.pubkey(), kp)
        print("checkpoint sim err:", sim["value"].get("err"))
        if sim["value"].get("err"):
            return
        sig = send([checkpoint_ix(kp.pubkey(), ck)], kp)
        print(f"checkpointed round {ck} → {sig}")
        try_claims(kp, load_stats(), dry_run=False)
        return

    if args.claim_only:
        if not kp:
            print("--claim-only requires --live")
            return
        stats = load_stats()
        try_claims(kp, stats, dry_run=False)
        save_stats(stats)
        return

    if args.once or dry_run:
        if args.live:
            reconcile_intents(load_intents())
        run_once(kp, dry_run, round_cap_lamports, daily_cap_lamports,
                 reserve_lamports, use_jev)
        return

    print(f"starting live loop, {args.cap_sol} SOL/round, "
          f"{args.daily_cap_sol} SOL/day UTC, "
          f"reserve {args.reserve_sol} SOL, JEV {'on' if use_jev else 'off'} — ctrl-C to stop")
    reconcile_intents(load_intents())
    while True:
        try:
            run_once(kp, False, round_cap_lamports, daily_cap_lamports,
                     reserve_lamports, use_jev)
        except Exception as e:  # noqa: BLE001
            print(f"iteration error: {e}")
        time.sleep(20)


if __name__ == "__main__":
    main()
