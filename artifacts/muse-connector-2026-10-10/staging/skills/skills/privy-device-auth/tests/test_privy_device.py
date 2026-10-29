#!/usr/bin/env python3
"""Headless tests that need module-level monkeypatching (run by selftest only
in spirit — kept as a separate file so SKILL.md documents one test entry).

Covers, with all network faked:
  - sign-tx rejects invalid base64 before any network call
  - find_wallet rejects a wallet id not in the authenticated user's list
  - sign-message refuses a non-solana chain_type wallet
  - wallet_rpc does 401 -> refresh -> retry exactly ONCE (second 401 surfaces)
  - no path in the module can select a broadcast/send RPC method
"""
import argparse
import base64
import importlib.util
import os
import sys
import tempfile

SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "bin", "privy_device.py"
)

spec = importlib.util.spec_from_file_location("privy_device", SCRIPT)
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)

FAKE_KEY = None  # set in run() to a real throwaway P-256 key (test only)


def run():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    global FAKE_KEY
    throwaway = ec.generate_private_key(ec.SECP256R1())
    FAKE_KEY = base64.b64encode(
        throwaway.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    ).decode()
    fails = []

    def check(cond, name):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    tmpd = tempfile.mkdtemp(prefix="privy-device-auth-net-")
    pd.CONFIG_DIR, pd.SESSION_FILE = tmpd, os.path.join(tmpd, "session.enc")
    pd._keyring_module = lambda: None

    fake_sess = {
        "access_token": "fake-access",
        "refresh_token": "fake-refresh",
        "access_token_expires_at": "2099-01-01T00:00:00+00:00",
        "wallets": [
            {"id": "sol-wallet", "address": "SoLAddr1", "chain_type": "solana"},
            {"id": "evm-wallet", "address": "0xabc", "chain_type": "ethereum"},
        ],
    }

    # --- 1. sign-tx rejects invalid base64 before touching the network --------
    calls = []

    def no_net(*a, **k):
        calls.append((a, k))
        raise AssertionError("network must not be reached")

    pd._http = no_net
    try:
        pd.cmd_sign_tx(argparse.Namespace(wallet="sol-wallet", tx="!!!not-base64!!!"))
        check(False, "sign-tx invalid base64 rejected")
    except pd.PrivyError as e:
        check("base64" in str(e), "sign-tx invalid base64 rejected")
    check(not calls, "sign-tx invalid base64 makes no network call")

    # --- 2. find_wallet rejects unknown wallet ids ---------------------------
    pd.wallet_authenticate = lambda tok: pd.Authz(
        FAKE_KEY, "2099-01-01T00:00:00+00:00", fake_sess["wallets"]
    )
    pd._authz_cache = None
    try:
        pd.find_wallet(fake_sess, "attacker-wallet")
        check(False, "find_wallet rejects unknown wallet id")
    except pd.PrivyError as e:
        check("refusing to sign" in str(e), "find_wallet rejects unknown wallet id")

    # --- 3. sign-message refuses non-solana wallets ---------------------------
    try:
        pd.cmd_sign_message(
            argparse.Namespace(wallet="evm-wallet", message="hello")
        )
        check(False, "sign-message refuses non-solana wallet")
    except pd.PrivyError as e:
        check("not solana" in str(e), "sign-message refuses non-solana wallet")

    # --- 4. 401 -> refresh -> retry exactly once -------------------------------
    http_log = []

    def fake_http(method, path, *, body=None, headers=None, timeout=30):
        http_log.append((method, path, headers or {}))
        if path.endswith("/token") and body and body.get("grant_type") == "refresh_token":
            return 200, {
                "access_token": "refreshed-access",
                "refresh_token": "refreshed-refresh",
                "expires_in": 900,
            }
        if path.endswith("/rpc"):
            auth = (headers or {}).get("Authorization", "")
            if "fake-access" in auth:
                return 401, {"error": "unauthorized"}
            if "refreshed-access" in auth:
                if getattr(fake_http, "always_401", False):
                    return 401, {"error": "unauthorized"}
                if not hasattr(fake_http, "retried"):
                    fake_http.retried = True
                    return 200, {"data": {"signature": "sig123"}}
                return 401, {"error": "unauthorized"}
        return 404, {}

    pd._http = fake_http
    pd._authz_cache = None
    data, _ = pd.wallet_rpc(
        fake_sess,
        "sol-wallet",
        {"method": "signMessage", "params": {"message": "aGk=", "encoding": "base64"}},
    )
    check(data.get("signature") == "sig123", "401 triggers one refresh + retry")
    refresh_calls = [c for c in http_log if c[1].endswith("/token")]
    check(len(refresh_calls) == 1, "refresh happens exactly once")
    # Second 401 (refresh didn't help) must surface, not loop.
    fake_http.always_401 = True
    pd._authz_cache = None
    try:
        pd.wallet_rpc(
            fake_sess,
            "sol-wallet",
            {"method": "signMessage", "params": {"message": "aGk=", "encoding": "base64"}},
        )
        check(False, "persistent 401 surfaces an error")
    except pd.PrivyError as e:
        check("RPC failed" in str(e), "persistent 401 surfaces an error")
    rpc_calls = [c for c in http_log if c[1].endswith("/rpc")]
    check(len(rpc_calls) == 4, f"no retry loop (rpc calls: {len(rpc_calls)})")

    # --- 5. no broadcast/send method selectable --------------------------------
    src = open(SCRIPT, encoding="utf-8").read()
    check("signAndSendTransaction" not in src, "no broadcast method anywhere")
    check(
        '"method": "signMessage"' in src and '"method": "signTransaction"' in src,
        "only signMessage + signTransaction methods exist",
    )

    # --- 6. grant_type values ---------------------------------------------------
    check(
        pd.GRANT_TYPE_DEVICE == "urn:ietf:params:oauth:grant-type:device_code",
        "device grant_type is the RFC 8628 URN",
    )

    import shutil

    shutil.rmtree(tmpd, ignore_errors=True)
    print()
    if fails:
        print(f"NETWORK-MOCK TESTS: {len(fails)} FAILURES: {fails}")
        sys.exit(1)
    print("NETWORK-MOCK TESTS: all passed")


if __name__ == "__main__":
    run()
