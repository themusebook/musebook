#!/usr/bin/env python3
"""Backpack Exchange ED25519 canonical signing-string builder + self-test.

Reference only: performs NO authenticated network calls. Authenticated
trading is NOT enabled (see SKILL.md).

The self-test uses a HARDCODED THROWAWAY TEST SEED. It is a fixed test
vector for verifying the canonicalization logic only — it is never
persisted, never used against any real account, and must never be treated
as a real credential.
"""
import argparse
import base64
import sys

# --- THROWAWAY TEST VECTOR (not a real key; test use only) ---
_TEST_SEED_HEX = (
    "9d61b19deffd5a60ba844af492ec2cc4"
    "4449c5697b326919703bac031cae7f60"
)


def canonical_signing_string(instruction, params, timestamp_ms, window_ms=5000):
    """Build the canonical signing string.

    instruction=<instruction>&<alphabetically-sorted params>&timestamp=<ms>&window=<ms>
    Only include parameters actually sent. For orderId/clientId endpoints,
    pass exactly one of the two.
    """
    parts = [f"instruction={instruction}"]
    for k in sorted(params):
        parts.append(f"{k}={params[k]}")
    parts.append(f"timestamp={timestamp_ms}")
    parts.append(f"window={window_ms}")
    return "&".join(parts)


def batch_signing_string(orders, timestamp_ms, window_ms=5000):
    """Batch orders: one `instruction=orderExecute` prefix per
    alphabetically-ordered order payload, concatenated, then timestamp/window."""
    payloads = []
    for order in orders:
        inner = "&".join(f"{k}={order[k]}" for k in sorted(order))
        payloads.append(f"instruction=orderExecute&{inner}")
    return "&".join(payloads) + f"&timestamp={timestamp_ms}&window={window_ms}"


def sign_string(seed_bytes, signing_string):
    """Sign with an ED25519 seed; returns (verifying_key_b64, signature_b64).

    Requires pynacl. Never call with a real seed outside the Secure Vault flow.
    """
    from nacl.signing import SigningKey
    sk = SigningKey(seed_bytes)
    sig = sk.sign(signing_string.encode()).signature
    vk_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
    return vk_b64, base64.b64encode(sig).decode()


def verify_string(vk_b64, sig_b64, signing_string):
    from nacl.signing import VerifyKey
    vk = VerifyKey(base64.b64decode(vk_b64))
    vk.verify(base64.b64decode(sig_b64) + signing_string.encode())
    return True


def self_test():
    failures = []

    # (1) Canonical-string test against the documented orderCancel example.
    expected = ("instruction=orderCancel&orderId=28&symbol=BTC_USDT"
                "&timestamp=1614550000000&window=5000")
    got = canonical_signing_string(
        "orderCancel",
        {"symbol": "BTC_USDT", "orderId": "28"},  # deliberately unsorted input
        1614550000000,
        5000,
    )
    if got == expected:
        print("PASS: canonical signing string matches documented orderCancel example")
    else:
        failures.append("canonical string mismatch")
        print(f"FAIL: expected {expected!r}, got {got!r}")

    # Param-exclusion check: only actually-sent params appear.
    s = canonical_signing_string("orderCancel", {"clientId": "abc"}, 1, 5000)
    if s == "instruction=orderCancel&clientId=abc&timestamp=1&window=5000":
        print("PASS: single orderId/clientId param included exactly once")
    else:
        failures.append("param exclusion")
        print(f"FAIL: param exclusion produced {s!r}")

    # Batch check: one instruction=orderExecute prefix per order payload.
    b = batch_signing_string(
        [{"symbol": "SOL_USDC", "side": "Bid", "orderType": "Limit",
          "quantity": "1", "price": "100"}],
        1614550000000, 5000,
    )
    if b.startswith("instruction=orderExecute&") and b.endswith("&timestamp=1614550000000&window=5000"):
        print("PASS: batch orderExecute prefix/timestamp form")
    else:
        failures.append("batch form")
        print(f"FAIL: batch form produced {b!r}")

    # (2) Signature round-trip against the derived verifying key.
    try:
        import nacl  # noqa: F401
    except ImportError:
        print("NOTE: pynacl not installed — string-canonicalization tests only. "
              "Signature bytes need `pynacl` (`pip install pynacl`).")
    else:
        seed = bytes.fromhex(_TEST_SEED_HEX)
        vk_b64, sig_b64 = sign_string(seed, expected)
        try:
            verify_string(vk_b64, sig_b64, expected)
            print(f"PASS: signature verifies against derived verifying key ({vk_b64[:12]}...)")
        except Exception as e:
            failures.append("signature verify")
            print(f"FAIL: signature did not verify: {e}")
        # Tamper check: altered string must NOT verify.
        try:
            verify_string(vk_b64, sig_b64, expected + "tampered")
            failures.append("tamper check")
            print("FAIL: tampered string verified (must not happen)")
        except Exception:
            print("PASS: tampered signing string correctly rejected")

    if failures:
        print(f"\nSELF-TEST FAILED: {failures}")
        return 1
    print("\nSELF-TEST OK — no network calls made, throwaway test key only.")
    return 0


def main():
    p = argparse.ArgumentParser(description="Backpack ED25519 signing-string reference.")
    p.add_argument("--self-test", action="store_true", help="Run the canonicalization self-test")
    a = p.parse_args()
    if a.self_test:
        sys.exit(self_test())
    p.print_help()


if __name__ == "__main__":
    main()
