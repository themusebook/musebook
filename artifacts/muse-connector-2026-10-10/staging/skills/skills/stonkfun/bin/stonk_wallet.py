#!/usr/bin/env python3
"""Local Stonkfun launcher wallet — user-approved exception (2026-09-18).

Scoped to Stonkfun/LaunchLab token launches ONLY:
  - initialize_with_token2022 against the Raydium LaunchLab program
  - (no swaps, no transfers, no other programs)

The 64-byte Solana secret is encrypted at rest with scrypt (N=2^15, r=8, p=1)
key derivation + XSalsa20-Poly1305 (PyNaCl secretbox). File is 0600.

The wallet password is NEVER stored — it is supplied transiently per session
and lives only in process memory while signing.

Policy:
  - Stonkfun/LaunchLab launches only (program id pinned in stonk_exec.py)
  - Per-launch approval: exact terms approved in chat + --confirm flag
  - Per-launch cost cap: 0.10 SOL (rent + fees; no launch fee on this path)
  - Daily cap: 1 SOL (UTC day), tracked in stonk-launcher-state.json
  - No dev buys in v1 (launch only)

Usage:
  stonk_wallet.py create [--password-stdin]   # generate + encrypt (prompts if tty)
  stonk_wallet.py pubkey                       # print public key (no password)
"""
import base64
import getpass
import json
import os
import sys

WALLET_PATH = os.environ.get("STONK_WALLET_PATH") or os.path.join(
    os.path.expanduser("~"), ".vulcan", "wallets", "stonk-launcher.json")

SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1


def _derive_key(password: bytes, salt: bytes) -> bytes:
    from nacl.bindings import (
        crypto_pwhash_scryptsalsa208sha256_ll,
        crypto_pwhash_scryptsalsa208sha256_SALTBYTES as SALT_LEN,
    )
    if len(salt) != SALT_LEN:
        raise ValueError("bad salt length")
    return crypto_pwhash_scryptsalsa208sha256_ll(
        password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, dklen=32,
        maxmem=64 * 1024 * 1024)


def encrypt_secret(secret: bytes, password: str) -> dict:
    import nacl.utils
    from nacl.secret import SecretBox
    salt = nacl.utils.random(32)
    key = _derive_key(password.encode(), salt)
    box = SecretBox(key)
    nonce = nacl.utils.random(SecretBox.NONCE_SIZE)
    ct = box.encrypt(secret, nonce).ciphertext
    b64 = lambda b: base64.b64encode(b).decode()
    return {"kdf": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
            "salt": b64(salt), "nonce": b64(nonce), "ciphertext": b64(ct)}


def decrypt_secret(enc: dict, password: str) -> bytes:
    from nacl.secret import SecretBox
    key = _derive_key(password.encode(), base64.b64decode(enc["salt"]))
    box = SecretBox(key)
    return box.decrypt(base64.b64decode(enc["ciphertext"]),
                       base64.b64decode(enc["nonce"]))


def create_wallet(path: str, password: str) -> str:
    from solders.keypair import Keypair
    kp = Keypair()
    secret = bytes(kp)  # 64-byte secret
    if len(secret) != 64:
        raise RuntimeError("unexpected secret length %d" % len(secret))
    pubkey = str(kp.pubkey())
    assert str(Keypair.from_bytes(secret).pubkey()) == pubkey
    data = {
        "name": "stonk-launcher",
        "public_key": pubkey,
        "encrypted": encrypt_secret(secret, password),
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "policy": ("Stonkfun/LaunchLab launches only. Per-launch chat approval + "
                   "--confirm. Per-launch cap 0.10 SOL, daily cap 1 SOL (UTC). "
                   "Password never stored; supplied transiently per session."),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(path, 0o600)
    return pubkey


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("create", "pubkey"):
        print(__doc__.strip())
        return 2
    if sys.argv[1] == "pubkey":
        d = json.load(open(WALLET_PATH))
        print(d["public_key"])
        return 0
    # create
    if os.path.exists(WALLET_PATH):
        print(f"Wallet already exists at {WALLET_PATH}; refusing to overwrite.")
        return 1
    if "--password-stdin" in sys.argv:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("New stonk-launcher wallet password: ")
        if getpass.getpass("Confirm: ") != password:
            print("Passwords do not match.")
            return 1
    if not password:
        print("Empty password refused.")
        return 1
    pubkey = create_wallet(WALLET_PATH, password)
    print(f"Created stonk-launcher wallet: {pubkey}")
    print("Fund it with SOL before launching. Password was NOT stored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
