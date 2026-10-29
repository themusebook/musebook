#!/usr/bin/env python3
"""Local DFlow trading wallet — user-approved exception (2026-09-18).

The 64-byte Solana secret is encrypted at rest with scrypt (N=2^15, r=8, p=1)
key derivation + XSalsa20-Poly1305 (PyNaCl secretbox). File is 0600.

The wallet password is NEVER stored — it is supplied transiently per session
and lives only in process memory while signing.

Usage:
  dflow_wallet.py create [--password-stdin]   # generate + encrypt (prompts if tty)
  dflow_wallet.py pubkey                       # print public key (no password)
"""
import base64
import getpass
import json
import os
import sys

WALLET_PATH = os.environ.get("DFLOW_WALLET_PATH") or os.path.join(
    os.path.expanduser("~"), ".vulcan", "wallets", "dflow-trader.json")

SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LEN = 32


def _derive_key(password: bytes, salt: bytes) -> bytes:
    # Raw scrypt via libsodium: N=2^15, r=8, p=1 (~33MB, fast enough per sign).
    from nacl.bindings import (
        crypto_pwhash_scryptsalsa208sha256_ll,
        crypto_pwhash_scryptsalsa208sha256_SALTBYTES as SALT_LEN,
    )
    if len(salt) != SALT_LEN:
        raise ValueError("bad salt length")
    return crypto_pwhash_scryptsalsa208sha256_ll(
        password, salt, 2 ** 15, 8, 1, dklen=32, maxmem=64 * 1024 * 1024)


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
    secret = bytes(kp)
    if len(secret) != 64:
        raise RuntimeError("unexpected secret length %d" % len(secret))
    pubkey = str(kp.pubkey())
    # verify re-derivation before encrypting
    assert str(Keypair.from_bytes(secret).pubkey()) == pubkey
    data = {
        "name": "dflow-trader",
        "public_key": pubkey,
        "encrypted": encrypt_secret(secret, password),
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "policy": "DFlow spot trading only. Password never stored; "
                  "supplied transiently per session.",
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    # round-trip check
    assert str(load_keypair(path, password).pubkey()) == pubkey
    return pubkey


def load_keypair(path: str, password: str):
    from solders.keypair import Keypair
    with open(path) as f:
        data = json.load(f)
    secret = decrypt_secret(data["encrypted"], password)
    return Keypair.from_bytes(secret)


def _read_password(use_stdin: bool) -> str:
    if use_stdin:
        pw = sys.stdin.readline().rstrip("\n")
    else:
        pw = getpass.getpass("dflow-trader wallet password: ")
    if not pw:
        raise SystemExit("empty password refused")
    return pw


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("create", "pubkey"):
        print(__doc__, file=sys.stderr)
        return 2
    if sys.argv[1] == "pubkey":
        with open(WALLET_PATH) as f:
            print(json.load(f)["public_key"])
        return 0
    # create
    if os.path.exists(WALLET_PATH):
        print("error: %s already exists — refusing to overwrite" % WALLET_PATH,
              file=sys.stderr)
        return 1
    use_stdin = "--password-stdin" in sys.argv or not sys.stdin.isatty()
    pw = _read_password(use_stdin)
    if not use_stdin:
        pw2 = getpass.getpass("confirm password: ")
        if pw != pw2:
            print("error: passwords do not match", file=sys.stderr)
            return 1
    pubkey = create_wallet(WALLET_PATH, pw)
    # scrub
    del pw
    try:
        del pw2
    except NameError:
        pass
    print("created dflow-trader wallet: %s" % pubkey)
    print("fund it with SOL before trading. Password was not stored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
