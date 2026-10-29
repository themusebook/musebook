#!/usr/bin/env python3
"""Privy OAuth 2.0 Device Authorization Grant — agent/CLI side for Musebook.

Lets a headless agent (CLI, cron job, autonomous process) act on a user's
Privy embedded wallets after a one-time browser approval. No app secret is
required or used anywhere; the user approves at the verification page and the
agent only ever holds short-lived tokens plus an ephemeral HPKE-decrypted
authorization key (memory only, never disk).

Flow:
  1. `login`            -> device_authorization -> show verification URL + code
  2. user approves at   -> https://musebook.trade/authorize
  3. agent polls token  -> access_token (15 min) + refresh_token (30 days, rotated)
  4. wallets/authenticate with an HPKE P-256/ChaCha20Poly1305 keypair
     -> decrypted authorization key (P-256, memory only) + wallet list
  5. wallet RPC calls are authorized with an ECDSA signature over the
     canonicalized request (RFC 8785 JCS, SHA-256, DER, base64) sent as
     `privy-authorization-signature`, plus `privy-grant-type: device_code`.

Security rules enforced here:
  - Tokens and the decrypted authorization key are NEVER printed, logged,
    or written to the repo. Error output is redacted to status + error code.
  - The device_code is kept in memory only for the duration of `login`.
  - The wallet id is always checked against the wallet list returned for the
    authenticated user before any signing call.
  - `sign-tx` signs only; this tool can never broadcast a transaction.

Dependencies: Python 3 stdlib + `cryptography` (HPKE + ECDSA + AES-GCM).
`keyring` is used opportunistically for the OS keychain when importable and
backed; otherwise sessions fall back to a machine-bound AES-256-GCM file.
A `./.venv` next to this script is used automatically when `cryptography`
is not importable in the current interpreter.
"""

# ---------------------------------------------------------------------------
# Dependency bootstrap: prefer the skill-local venv when `cryptography`
# is not importable in the running interpreter.
# ---------------------------------------------------------------------------
import os
import sys


def _VENV_CANDIDATES():
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(os.path.dirname(here), ".venv", "bin", "python3"),
        os.path.expanduser("~/.venvs/privy-device-auth/bin/python3"),
    ]


def _ensure_deps() -> None:
    try:
        import cryptography  # noqa: F401
        return
    except ImportError:
        pass
    for venv_py in _VENV_CANDIDATES():
        venv_dir = os.path.dirname(os.path.dirname(venv_py))
        # Compare sys.prefix, not realpath(executable): a venv's python3 is a
        # symlink to the system python, so the realpaths are identical while
        # the venv context (pyvenv.cfg -> site-packages) only applies when
        # launched via the venv path.
        if os.path.isfile(venv_py) and os.path.realpath(
            sys.prefix
        ) != os.path.realpath(venv_dir):
            os.execv(venv_py, [venv_py] + sys.argv)
    sys.exit(
        "error: the 'cryptography' package is required.\n"
        "Install it with:\n"
        "  python3 -m venv ~/.venvs/privy-device-auth && "
        "~/.venvs/privy-device-auth/bin/pip install cryptography keyring\n"
        "or: python3 -m venv .venv && .venv/bin/pip install cryptography keyring\n"
        "(run from the skill directory for the .venv option)"
    )


_ensure_deps()

# ---------------------------------------------------------------------------
# Imports (stdlib + cryptography only)
# ---------------------------------------------------------------------------
import argparse
import base64
import binascii
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_ID = os.environ.get("PRIVY_APP_ID", "cm7tbyvvy01w2144yss67bjm0")
BASE_URL = os.environ.get("PRIVY_API_BASE_URL", "https://auth.privy.io").rstrip("/")
VERIFY_PAGE = "https://musebook.trade/authorize"
# OAuth 2.0 device grant type. Privy's docs show the short form "device_code";
# Privy's own official agent CLI sends the full URN, so we do too.
GRANT_TYPE_DEVICE = "urn:ietf:params:oauth:grant-type:device_code"
GRANT_TYPE_REFRESH = "refresh_token"
USER_AGENT = "privy-device-auth/1.0 (+https://musebook.trade)"
# Refresh proactively this many seconds before a token expires.
EXPIRY_SKEW = 60

KEYRING_SERVICE = "privy-device-auth"
KEYRING_ACCOUNT = "musebook-session"
CONFIG_DIR = os.path.expanduser("~/.config/privy-device-auth")
SESSION_FILE = os.path.join(CONFIG_DIR, "session.enc")


class PrivyError(Exception):
    """Raised for protocol-level failures (message text is safe to show)."""


# ---------------------------------------------------------------------------
# HTTP layer (urllib, honest UA, redacted errors)
# ---------------------------------------------------------------------------
def _http(
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Tuple[int, Any]:
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "privy-app-id": APP_ID,
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read() or b"{}")
        except Exception:
            payload = {}
        return e.code, payload
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise PrivyError(f"network error calling {path}: {e}")


def _err(payload: Any, status: int) -> str:
    """Redacted one-line error: status + server error code only, never bodies."""
    if isinstance(payload, dict):
        code = payload.get("error")
        if isinstance(code, str) and code:
            return f"HTTP {status}: {code}"
    return f"HTTP {status}"


# ---------------------------------------------------------------------------
# Session storage: OS keychain via `keyring` when available, else a
# machine-bound AES-256-GCM file (0600) with a loud warning. The decrypted
# wallet authorization key is NEVER persisted here — memory only.
# ---------------------------------------------------------------------------
def _keyring_module():
    try:
        import keyring
        import keyring.backends.fail  # noqa: F401

        kr = keyring.get_keyring()
        if isinstance(kr, keyring.backends.fail.Keyring):
            return None
        return keyring
    except Exception:
        return None


def _warn_file_fallback() -> None:
    print(
        "WARNING: OS keychain unavailable — session stored in an encrypted file instead.",
        file=sys.stderr,
    )
    print(
        f"WARNING: {SESSION_FILE} (mode 0600, encryption key bound to this machine). "
        "Prefer a host with an OS keychain (macOS Keychain / Secret Service / "
        "Windows Credential Manager) for stronger protection.",
        file=sys.stderr,
    )


def _machine_id() -> Optional[str]:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                return value
        except OSError:
            continue
    return None


def _file_key() -> bytes:
    """Machine-bound file encryption key.

    Mirrors Privy's official agent CLI: HKDF-SHA256 over the machine identity,
    salt b"privy-device-auth", info b"session-encryption", 32 bytes. This
    stops other local users from reading the file; it does not stop root or
    a full disk compromise. The OS keychain remains the preferred backend.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    mid = _machine_id()
    if mid is None:
        import socket

        material = f"{socket.gethostname()}::{os.path.expanduser('~')}".encode("utf-8")
    else:
        material = mid.encode("utf-8")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"privy-device-auth",
        info=b"session-encryption",
    ).derive(material)


def _file_write(session_json: str) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass
    nonce = os.urandom(12)
    sealed = AESGCM(_file_key()).encrypt(nonce, session_json.encode("utf-8"), None)
    body, tag = sealed[:-16], sealed[-16:]
    blob = base64.b64encode(nonce + tag + body).decode("ascii")
    fd = os.open(SESSION_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(blob)
    try:
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass
    _warn_file_fallback()


def _file_read() -> Optional[str]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            blob = f.read().strip()
    except OSError:
        return None
    try:
        raw = base64.b64decode(blob)
        nonce, tag, body = raw[:12], raw[12:28], raw[28:]
        plain = AESGCM(_file_key()).decrypt(nonce, body + tag, None)
        _warn_file_fallback()
        return plain.decode("utf-8")
    except Exception:
        return None


def _file_delete() -> None:
    try:
        os.unlink(SESSION_FILE)
    except OSError:
        pass


def storage_backend() -> str:
    """Which backend currently holds (or would hold) the session. No secrets."""
    kr = _keyring_module()
    if kr is not None:
        try:
            if kr.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT):
                return "keyring"
        except Exception:
            pass
        # keyring importable but unusable -> would fall back to file
        return "keyring" if _keyring_usable(kr) else "file"
    return "file" if os.path.exists(SESSION_FILE) else "none"


def _keyring_usable(kr) -> bool:
    try:
        kr.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT + ".__probe__")
        return True
    except Exception:
        return False


def session_load() -> Optional[Dict[str, Any]]:
    kr = _keyring_module()
    if kr is not None:
        try:
            value = kr.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
            if value:
                return json.loads(value)
        except Exception:
            pass
    value = _file_read()
    if not value:
        return None
    try:
        sess = json.loads(value)
    except Exception:
        return None
    # Opportunistically migrate file -> keychain (mirrors official CLI).
    if kr is not None:
        try:
            kr.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, value)
            _file_delete()
        except Exception:
            pass
    return sess


def session_save(sess: Dict[str, Any]) -> str:
    raw = json.dumps(sess)
    kr = _keyring_module()
    if kr is not None:
        try:
            kr.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, raw)
            _file_delete()
            return "keyring"
        except Exception:
            pass
    _file_write(raw)
    return "file"


def session_delete() -> None:
    kr = _keyring_module()
    if kr is not None:
        try:
            kr.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception:
            pass
    _file_delete()


# ---------------------------------------------------------------------------
# Token lifecycle
# ---------------------------------------------------------------------------
def _is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return True
    try:
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
    except Exception:
        return True
    return exp <= datetime.now(timezone.utc) + timedelta(seconds=EXPIRY_SKEW)


def refresh_session(sess: Dict[str, Any]) -> Dict[str, Any]:
    """Exchange the refresh token. The server ROTATES it: the new pair is
    persisted immediately — losing it silently loses access."""
    status, payload = _http(
        "POST",
        "/api/oauth/v2/token",
        body={"grant_type": GRANT_TYPE_REFRESH, "refresh_token": sess["refresh_token"]},
    )
    if status != 200:
        raise PrivyError(
            "session expired and refresh failed "
            f"({_err(payload, status)}). Run `login` again."
        )
    try:
        new_access = payload["access_token"]
        new_refresh = payload["refresh_token"]
        expires_in = int(payload.get("expires_in", 900))
    except (KeyError, ValueError, TypeError):
        raise PrivyError("unexpected token refresh response from Privy")
    sess = dict(sess)
    sess["access_token"] = new_access
    sess["refresh_token"] = new_refresh
    sess["access_token_expires_at"] = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()
    session_save(sess)
    global _authz_cache
    _authz_cache = None
    return sess


def ensure_session() -> Dict[str, Any]:
    sess = session_load()
    if not sess:
        raise PrivyError("not logged in. Run `login` first.")
    if _is_expired(sess.get("access_token_expires_at")):
        sess = refresh_session(sess)
    return sess


# ---------------------------------------------------------------------------
# Wallet authentication: HPKE (P-256 / HKDF-SHA256 / ChaCha20-Poly1305, the
# exact suite Privy's official agent CLI uses). The decrypted authorization
# key lives in process memory only and is cached until `expires_at`.
# ---------------------------------------------------------------------------
class Authz(NamedTuple):
    key: str  # PEM or base64-PKCS8 P-256 private key (MEMORY ONLY)
    expires_at: str
    wallets: List[Dict[str, Any]]


_authz_cache: Optional[Tuple[str, str, List[Dict[str, Any]]]] = None


def wallet_authenticate(access_token: str) -> Authz:
    from cryptography.hazmat.primitives import hpke
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    priv = ec.generate_private_key(ec.SECP256R1())
    spki_der = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    recipient_b64 = base64.b64encode(spki_der).decode("ascii")

    status, payload = _http(
        "POST",
        "/api/oauth/v2/wallets/authenticate",
        headers={
            "Authorization": f"Bearer {access_token}",
            "privy-grant-type": "device_code",
        },
        body={"encryption_type": "HPKE", "recipient_public_key": recipient_b64},
    )
    if status != 200:
        raise PrivyError(f"wallet authentication failed: {_err(payload, status)}")
    try:
        enc_key = payload["encrypted_authorization_key"]
        enc = base64.b64decode(enc_key["encapsulated_key"])
        ct = base64.b64decode(enc_key["ciphertext"])
        expires_at = payload["expires_at"]
        wallets = payload.get("wallets") or []
    except (KeyError, TypeError, binascii.Error) as e:
        raise PrivyError(f"unexpected wallets/authenticate response: {e}")

    suite = hpke.Suite(hpke.KEM.P256, hpke.KDF.HKDF_SHA256, hpke.AEAD.CHACHA20_POLY1305)
    try:
        # cryptography's simplified HPKE API takes enc||ciphertext as one blob.
        plain = suite.decrypt(enc + ct, priv)
    except Exception as e:
        raise PrivyError(f"HPKE decryption of the authorization key failed: {e}")
    try:
        key_str = plain.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise PrivyError("authorization key is not UTF-8 text; refusing to use it")
    if not key_str:
        raise PrivyError("empty authorization key returned by Privy")
    return Authz(key_str, expires_at, wallets)


def ensure_authz(sess: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Return (key, expires_at, wallets), refreshing via wallets/authenticate
    when the in-memory cache is missing or expired. Never touches disk."""
    global _authz_cache
    valid = False
    if _authz_cache is not None:
        valid = not _is_expired(_authz_cache[1])
    if not valid:
        authz = wallet_authenticate(sess["access_token"])
        _authz_cache = (authz.key, authz.expires_at, authz.wallets)
        if authz.wallets:
            updated = dict(sess)
            updated["wallets"] = authz.wallets
            session_save(updated)
    assert _authz_cache is not None
    return _authz_cache


def find_wallet(sess: Dict[str, Any], wallet_id: str) -> Dict[str, Any]:
    """Confirm the wallet id belongs to the authenticated user. Refuses
    anything not present in the wallet list Privy returned for this grant."""
    _, _, wallets = ensure_authz(sess)
    for w in wallets:
        if w.get("id") == wallet_id:
            return w
    raise PrivyError(
        f"wallet '{wallet_id}' is not in this session's wallet list; refusing to sign."
    )


# ---------------------------------------------------------------------------
# Request authorization signatures.
# Verified against Privy's official agent CLI (v0.3.6) and go-sdk:
#   input  = {version:1, method:"POST", url, body, headers:{"privy-app-id":...}}
#   bytes  = RFC 8785 JCS canonical JSON ({} body becomes "")
#   sig    = base64(DER(ECDSA_P256(SHA256(bytes))))
# The HTTP request additionally carries privy-grant-type: device_code, which
# is NOT part of the signed headers (matches the official CLI exactly).
# ---------------------------------------------------------------------------
def _jcs(obj: Any) -> bytes:
    # RFC 8785 for our payloads: ASCII keys/strings, ints, nested dicts.
    # sort_keys + no whitespace + UTF-8 is byte-identical to JCS here.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _load_p256_private_key(key_str: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    if key_str.startswith("-----BEGIN"):
        key = serialization.load_pem_private_key(key_str.encode("utf-8"), password=None)
    else:
        key = serialization.load_der_private_key(
            base64.b64decode(key_str), password=None
        )
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
        key.curve, ec.SECP256R1
    ):
        raise PrivyError("authorization key is not a P-256 private key")
    return key


def authorization_signature(authz_key: str, url: str, body: Dict[str, Any]) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    body_for_sig: Any = body
    if not body:
        body_for_sig = ""
    else:
        # go-sdk rule: a body that marshals to {} is signed as "".
        body_for_sig = "" if _jcs(body) == b"{}" else body
    payload = {
        "version": 1,
        "method": "POST",
        "url": url,
        "body": body_for_sig,
        "headers": {"privy-app-id": APP_ID},
    }
    digest = hashlib.sha256(_jcs(payload)).digest()
    private_key = _load_p256_private_key(authz_key)
    sig_der = private_key.sign(digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    return base64.b64encode(sig_der).decode("ascii")


def wallet_rpc(
    sess: Dict[str, Any], wallet_id: str, body: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """POST an authorized wallet RPC. Returns (response_data, session).
    On 401 the tokens are refreshed once and the call retried once."""
    wallet = find_wallet(sess, wallet_id)
    if wallet.get("chain_type") != "solana":
        raise PrivyError(
            f"wallet '{wallet_id}' is chain_type '{wallet.get('chain_type')}', "
            "not solana; refusing."
        )
    path = f"/api/oauth/v2/wallets/{wallet_id}/rpc"
    url = BASE_URL + path

    def _call(access_token: str, authz_key: str) -> Tuple[int, Any]:
        sig = authorization_signature(authz_key, url, body)
        return _http(
            "POST",
            path,
            headers={
                "Authorization": f"Bearer {access_token}",
                "privy-grant-type": "device_code",
                "privy-authorization-signature": sig,
            },
            body=body,
        )

    authz_key, _, _ = ensure_authz(sess)
    status, payload = _call(sess["access_token"], authz_key)
    if status == 401:
        sess = refresh_session(sess)
        authz_key, _, _ = ensure_authz(sess)
        find_wallet(sess, wallet_id)  # re-confirm after refresh
        status, payload = _call(sess["access_token"], authz_key)
    if status != 200:
        raise PrivyError(f"wallet RPC failed: {_err(payload, status)}")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise PrivyError("unexpected wallet RPC response shape")
    return data, sess


# ---------------------------------------------------------------------------
# Device-flow polling: pure decision function (unit-testable) + driver.
# ---------------------------------------------------------------------------
def _poll_action(status: int, payload: Any) -> Tuple[str, str]:
    """Classify one token-poll response.

    Returns (action, detail) where action is one of:
      done | wait | slow_down | expired | denied | fatal
    """
    if status == 200:
        return "done", ""
    err = payload.get("error") if isinstance(payload, dict) else None
    if err == "authorization_pending":
        return "wait", ""
    if err == "slow_down":
        return "slow_down", ""
    if err == "expired_token":
        return "expired", ""
    if err == "access_denied":
        return "denied", ""
    return "fatal", _err(payload, status)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def _http_retry(
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    attempts: int = 5,
    timeout: int = 30,
) -> Tuple[int, Any]:
    """_http with exponential-backoff retry on transient transport failures.

    Some egress paths (corporate proxies, flaky NAT) intermittently reset
    the TLS connection to Privy; the device flow is cheap and idempotent
    here, so retry instead of failing the whole login.
    """
    delay = 1.0
    last: Optional[PrivyError] = None
    for i in range(attempts):
        try:
            return _http(method, path, body=body, headers=headers, timeout=timeout)
        except PrivyError as e:
            last = e
            if i < attempts - 1:
                time.sleep(delay)
                delay *= 2.0
    assert last is not None
    raise last


def cmd_login(_args: argparse.Namespace) -> None:
    status, payload = _http_retry(
        "POST", "/api/oauth/v2/device_authorization", body={}
    )
    if status != 200:
        if status == 403 and isinstance(payload, dict) and payload.get("error") == (
            "device_auth_not_enabled"
        ):
            raise PrivyError(
                "device authorization is not enabled for this Privy app "
                "(dashboard: Authentication -> Advanced -> CLI and agent access)."
            )
        raise PrivyError(f"device authorization failed: {_err(payload, status)}")
    try:
        device_code = payload["device_code"]  # kept in memory only, never printed
        user_code = payload["user_code"]
        verification_uri = payload.get("verification_uri_complete") or payload.get(
            "verification_uri"
        )
        expires_in = int(payload.get("expires_in", 600))
        interval = int(payload.get("interval", 5))
    except (KeyError, ValueError, TypeError):
        raise PrivyError("unexpected device_authorization response from Privy")

    print()
    print("  To authorize this agent, visit:")
    print(f"    {verification_uri}")
    print("  and enter the code:")
    print(f"    {user_code}")
    print()
    print(
        "Approve the request in your browser (log in with Privy if asked). "
        "Waiting for approval..."
    )

    deadline = time.time() + expires_in
    wait = max(interval, 5)
    tokens: Optional[Dict[str, Any]] = None
    while time.time() < deadline:
        time.sleep(wait)
        try:
            status, payload = _http(
                "POST",
                "/api/oauth/v2/token",
                body={"grant_type": GRANT_TYPE_DEVICE, "device_code": device_code},
            )
        except PrivyError as e:
            # Transient transport failure (connection reset, DNS blip, ...).
            # The device code is still valid until the deadline, so keep
            # polling instead of aborting the whole login.
            print(f"  (poll request failed, retrying: {e})", file=sys.stderr)
            continue
        action, detail = _poll_action(status, payload)
        if action == "done":
            tokens = payload
            break
        if action == "wait":
            continue
        if action == "slow_down":
            wait += 5
            continue
        if action == "expired":
            raise PrivyError("device code expired. Run `login` again.")
        if action == "denied":
            raise PrivyError("authorization request was denied in the browser.")
        raise PrivyError(f"token polling failed: {detail}")
    if tokens is None:
        raise PrivyError("device code expired. Run `login` again.")

    try:
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        token_expires_in = int(tokens.get("expires_in", 900))
    except (KeyError, ValueError, TypeError):
        raise PrivyError("unexpected token response from Privy")

    sess: Dict[str, Any] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_token_expires_at": (
            datetime.now(timezone.utc) + timedelta(seconds=token_expires_in)
        ).isoformat(),
        "wallets": [],
    }
    # Verify the grant end-to-end and capture the wallet list.
    authz = wallet_authenticate(access_token)
    global _authz_cache
    _authz_cache = (authz.key, authz.expires_at, authz.wallets)
    sess["wallets"] = authz.wallets
    backend = session_save(sess)

    print()
    print("Logged in. Wallets on this grant:")
    if authz.wallets:
        for w in authz.wallets:
            print(f"  {w.get('chain_type')}: {w.get('address')} ({w.get('id')})")
    else:
        print("  (none yet — create one in the Privy dashboard or app)")
    print(f"Session stored via: {backend}")
    print("Access token: 15 min. Refresh token: 30 days (auto-rotated).")


def cmd_status(_args: argparse.Namespace) -> None:
    sess = session_load()
    if not sess:
        print("not logged in (no session stored)")
        return
    # Never print token values — presence and expiry only.
    exp = sess.get("access_token_expires_at")
    remaining = "unknown"
    try:
        dt = datetime.fromisoformat(exp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = dt - datetime.now(timezone.utc)
        remaining = (
            f"{int(delta.total_seconds() // 60)}m {int(delta.total_seconds() % 60)}s"
            if delta.total_seconds() > 0
            else "expired"
        )
    except Exception:
        pass
    wallets = sess.get("wallets") or []
    print(f"logged in: yes (storage: {storage_backend()})")
    print(f"access token: present, expires in ~{remaining}")
    print(f"refresh token: {'present' if sess.get('refresh_token') else 'missing'}")
    print(f"wallets cached: {len(wallets)}")
    for w in wallets:
        print(f"  {w.get('chain_type')}: {w.get('address')} ({w.get('id')})")


def cmd_wallets(_args: argparse.Namespace) -> None:
    sess = ensure_session()
    _, _, wallets = ensure_authz(sess)
    if not wallets:
        print("no wallets on this grant")
        return
    for w in wallets:
        print(f"{w.get('chain_type')}: {w.get('address')} ({w.get('id')})")


def cmd_sign_message(args: argparse.Namespace) -> None:
    sess = ensure_session()
    message = args.message.encode("utf-8")
    body = {
        "method": "signMessage",
        # params.encoding="base64" is required by Privy's Solana RPC surface.
        "params": {
            "message": base64.b64encode(message).decode("ascii"),
            "encoding": "base64",
        },
    }
    data, _ = wallet_rpc(sess, args.wallet, body)
    sig = data.get("signature")
    if not sig:
        raise PrivyError("unexpected signMessage response (no signature field)")
    print(sig)


def cmd_sign_tx(args: argparse.Namespace) -> None:
    # Validate locally before touching the session/network: fail fast.
    try:
        tx_bytes = base64.b64decode(args.tx, validate=True)
    except (binascii.Error, ValueError):
        raise PrivyError("--tx must be valid base64 of a serialized Solana transaction")
    if not tx_bytes:
        raise PrivyError("--tx decoded to empty bytes")
    sess = ensure_session()
    body = {
        "method": "signTransaction",
        "params": {
            "transaction": base64.b64encode(tx_bytes).decode("ascii"),
            "encoding": "base64",
        },
    }
    data, _ = wallet_rpc(sess, args.wallet, body)
    signed = (
        data.get("signed_transaction")
        or data.get("signedTransaction")
        or data.get("transaction")
    )
    if not signed:
        raise PrivyError("unexpected signTransaction response (no signed transaction)")
    # This tool signs only. It can never broadcast: there is deliberately
    # no transaction-submission path in this skill.
    print("# Signed transaction (base64). NOT broadcast.")
    print("# Submit via your own Solana RPC only with explicit user approval.")
    print(signed)


def cmd_revoke(args: argparse.Namespace) -> None:
    """Audit / revoke agent authorizations.

    Grant listing and revocation are user-scoped operations: they require a
    browser-derived Privy USER access token, NOT the stored device-grant
    access token. The token is read from the clearly named environment
    variable PRIVY_USER_ACCESS_TOKEN or from a non-echoing prompt, and is
    never stored or printed.

    Effect: revocation invalidates refresh tokens immediately. An access JWT
    minted before revocation may remain valid for up to ~15 minutes.
    """
    token = os.environ.get("PRIVY_USER_ACCESS_TOKEN")
    if not token:
        import getpass

        print("Grant audit/revocation needs a browser-derived Privy user access")
        print("token (from a signed-in web session, not the device grant).")
        token = getpass.getpass("Privy user access token: ").strip()
    if not token:
        raise PrivyError("no user access token provided")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        if args.grant_id:
            confirm = input(
                f"Revoke grant {args.grant_id}? Type YES to confirm: "
            ).strip()
            if confirm != "YES":
                print("aborted")
                return
            status, payload = _http(
                "DELETE", f"/api/oauth/v2/grants/{args.grant_id}", headers=headers
            )
            if status not in (200, 204):
                raise PrivyError(f"revoking grant failed: {_err(payload, status)}")
            print(f"revoked grant {args.grant_id}")
            if payload:
                print(json.dumps(payload)[:200])
        else:
            status, payload = _http("GET", "/api/oauth/v2/grants", headers=headers)
            if status != 200:
                raise PrivyError(f"listing grants failed: {_err(payload, status)}")
            grants = payload.get("data") or []
            if not grants:
                print("no active grants")
                return
            print("Active agent authorizations for this user:")
            for g in grants:
                print(
                    f"  {g.get('id')}  grant_type={g.get('grant_type')}  "
                    f"created={g.get('created_at')}  last_used={g.get('last_used_at')}"
                )
            print("\nTo revoke one: privy_device.py revoke --grant-id <id>")
    finally:
        # Scrub the token from the process (best effort).
        token = "x" * len(token)


def cmd_logout(_args: argparse.Namespace) -> None:
    session_delete()
    print("logged out: stored session deleted")


# ---------------------------------------------------------------------------
# Self-test: everything testable without a human in a browser.
# ---------------------------------------------------------------------------
def _t_assert(cond: bool, name: str) -> None:
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        _t_assert.failed = True  # type: ignore[attr-defined]


_t_assert.failed = False  # type: ignore[attr-defined]


def cmd_selftest(_args: argparse.Namespace) -> None:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    # 1. JCS canonicalization vector (byte-exact RFC 8785 for our payloads).
    sample = {
        "version": 1,
        "method": "POST",
        "url": "https://auth.privy.io/api/oauth/v2/wallets/wallet_abc/rpc",
        "body": {
            "method": "signMessage",
            "params": {"encoding": "base64", "message": "aGVsbG8="},
        },
        "headers": {"privy-app-id": "cm7tbyvvy01w2144yss67bjm0"},
    }
    expected = (
        b'{"body":{"method":"signMessage","params":{"encoding":"base64",'
        b'"message":"aGVsbG8="}},"headers":{"privy-app-id":'
        b'"cm7tbyvvy01w2144yss67bjm0"},"method":"POST",'
        b'"url":"https://auth.privy.io/api/oauth/v2/wallets/wallet_abc/rpc",'
        b'"version":1}'
    )
    _t_assert(_jcs(sample) == expected, "jcs canonicalization vector")
    _t_assert(_jcs({}) == b"{}", "jcs empty object")

    # 2. Authorization-signature roundtrip: sign with P-256, verify.
    key = ec.generate_private_key(ec.SECP256R1())
    der = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    key_b64 = base64.b64encode(der).decode("ascii")
    pem = key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode("ascii")
    url = "https://auth.privy.io/api/oauth/v2/wallets/wallet_abc/rpc"
    for label, ks in (("base64-pkcs8", key_b64), ("pem", pem)):
        sig_b64 = authorization_signature(ks, url, sample["body"])
        sig_der = base64.b64decode(sig_b64)
        payload = {
            "version": 1,
            "method": "POST",
            "url": url,
            "body": sample["body"],
            "headers": {"privy-app-id": APP_ID},
        }
        digest = hashlib.sha256(_jcs(payload)).digest()
        try:
            key.public_key().verify(sig_der, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
            ok = True
        except Exception:
            ok = False
        _t_assert(ok, f"authorization signature verifies ({label})")
    # Empty-body rule: {} signs as "".
    s1 = authorization_signature(key_b64, url, {})
    _t_assert(isinstance(s1, str) and len(s1) > 0, "authorization signature empty body")
    _t_assert(_load_p256_private_key(key_b64) is not None, "p256 loader base64")
    _t_assert(_load_p256_private_key(pem) is not None, "p256 loader pem")

    # 3. HPKE roundtrip with Privy's exact suite (P-256 / HKDF-SHA256 / ChaCha20).
    from cryptography.hazmat.primitives import hpke

    suite = hpke.Suite(hpke.KEM.P256, hpke.KDF.HKDF_SHA256, hpke.AEAD.CHACHA20_POLY1305)
    hpke_priv = ec.generate_private_key(ec.SECP256R1())
    blob = suite.encrypt(b"fake-authorization-key", hpke_priv.public_key())
    n = hpke.KEM.P256.enc_length()
    pt = suite.decrypt(blob[:n] + blob[n:], hpke_priv)
    _t_assert(pt == b"fake-authorization-key", "hpke P-256/ChaCha20 roundtrip")
    spki = hpke_priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    _t_assert(len(base64.b64encode(spki)) > 0, "spki der base64 recipient key")

    # 4. Poll decision table.
    cases = [
        ((200, {}), "done"),
        ((400, {"error": "authorization_pending"}), "wait"),
        ((400, {"error": "slow_down"}), "slow_down"),
        ((400, {"error": "expired_token"}), "expired"),
        ((400, {"error": "access_denied"}), "denied"),
        ((400, {"error": "weird"}), "fatal"),
        ((500, {}), "fatal"),
    ]
    for (st, p), want in cases:
        got, _ = _poll_action(st, p)
        _t_assert(got == want, f"poll action {st}/{p.get('error') if isinstance(p, dict) else ''} -> {want}")

    # 5. Storage round-trip with a fake session (file backend, temp dir).
    import tempfile

    global CONFIG_DIR, SESSION_FILE
    tmpd = tempfile.mkdtemp(prefix="privy-device-auth-test-")
    old_dir, old_file = CONFIG_DIR, SESSION_FILE
    CONFIG_DIR, SESSION_FILE = tmpd, os.path.join(tmpd, "session.enc")
    # Force the file backend even if keyring exists.
    global _keyring_module
    real_keyring = _keyring_module
    _keyring_module = lambda: None  # noqa: E731
    try:
        fake = {
            "access_token": "fake-access",
            "refresh_token": "fake-refresh",
            "access_token_expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat(),
            "wallets": [{"id": "w1", "address": "A1", "chain_type": "solana"}],
        }
        # Capture the loud warning; it must go to stderr, not stdout.
        import io

        err_buf, out_buf = io.StringIO(), io.StringIO()
        old_err, old_out = sys.stderr, sys.stdout
        sys.stderr, sys.stdout = err_buf, out_buf
        try:
            backend = session_save(fake)
            loaded = session_load()
        finally:
            sys.stderr, sys.stdout = old_err, old_out
        _t_assert(backend == "file", "storage falls back to encrypted file")
        _t_assert(loaded == fake, "storage round-trip preserves session")
        _t_assert("WARNING" in err_buf.getvalue(), "file fallback warns loudly")
        _t_assert("fake-access" not in out_buf.getvalue(), "no secrets on stdout")
        mode = oct(os.stat(SESSION_FILE).st_mode & 0o777)
        _t_assert(mode == "0o600", f"session file is 0600 (got {mode})")
        raw_file = open(SESSION_FILE, encoding="utf-8").read()
        _t_assert("fake-access" not in raw_file, "session file is encrypted, not plaintext")
        session_delete()
        _t_assert(not os.path.exists(SESSION_FILE), "logout deletes session file")
    finally:
        _keyring_module = real_keyring
        CONFIG_DIR, SESSION_FILE = old_dir, old_file
        import shutil

        shutil.rmtree(tmpd, ignore_errors=True)

    # 6. Refresh rotation: the NEW refresh token must be persisted (mocked HTTP).
    real_http = globals()["_http"]
    seen_bodies: List[Dict[str, Any]] = []

    def fake_http(method, path, *, body=None, headers=None, timeout=30):
        seen_bodies.append(body or {})
        if path.endswith("/token"):
            return 200, {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 900,
            }
        return 404, {}

    globals()["_http"] = fake_http
    tmpd2 = tempfile.mkdtemp(prefix="privy-device-auth-test2-")
    CONFIG_DIR, SESSION_FILE = tmpd2, os.path.join(tmpd2, "session.enc")
    _keyring_module = lambda: None  # noqa: E731
    try:
        old_sess = {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "access_token_expires_at": (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).isoformat(),
            "wallets": [],
        }
        new_sess = refresh_session(old_sess)
        _t_assert(new_sess["refresh_token"] == "new-refresh", "refresh rotates token in memory")
        reloaded = session_load()
        _t_assert(
            reloaded is not None and reloaded["refresh_token"] == "new-refresh",
            "refresh persists the ROTATED refresh token",
        )
        _t_assert(
            reloaded is not None and reloaded["access_token"] == "new-access",
            "refresh persists the new access token",
        )
        _t_assert(
            seen_bodies and seen_bodies[0].get("refresh_token") == "old-refresh",
            "refresh sends the old refresh token",
        )
    finally:
        globals()["_http"] = real_http
        _keyring_module = real_keyring
        CONFIG_DIR, SESSION_FILE = old_dir, old_file
        import shutil

        shutil.rmtree(tmpd2, ignore_errors=True)

    # 7. Status output redaction (fake session, no secrets leaked).
    tmpd3 = tempfile.mkdtemp(prefix="privy-device-auth-test3-")
    CONFIG_DIR, SESSION_FILE = tmpd3, os.path.join(tmpd3, "session.enc")
    _keyring_module = lambda: None  # noqa: E731
    try:
        session_save(
            {
                "access_token": "SECRET-ACCESS-123",
                "refresh_token": "SECRET-REFRESH-456",
                "access_token_expires_at": (
                    datetime.now(timezone.utc) + timedelta(minutes=10)
                ).isoformat(),
                "wallets": [{"id": "w1", "address": "Addr1", "chain_type": "solana"}],
            }
        )
        import io

        buf = io.StringIO()
        old_out = sys.stdout
        sys.stdout = buf
        try:
            cmd_status(argparse.Namespace())
        finally:
            sys.stdout = old_out
        out = buf.getvalue()
        _t_assert("SECRET-ACCESS-123" not in out, "status redacts access token")
        _t_assert("SECRET-REFRESH-456" not in out, "status redacts refresh token")
        _t_assert("Addr1" in out, "status shows wallet address (not secret)")
    finally:
        _keyring_module = real_keyring
        CONFIG_DIR, SESSION_FILE = old_dir, old_file
        import shutil

        shutil.rmtree(tmpd3, ignore_errors=True)

    # 8. Arg parsing for every subcommand.
    ap = build_parser()
    _t_assert(ap.parse_args(["login"]).command == "login", "parse login")
    _t_assert(ap.parse_args(["status"]).command == "status", "parse status")
    _t_assert(ap.parse_args(["wallets"]).command == "wallets", "parse wallets")
    a = ap.parse_args(["sign-message", "--wallet", "w1", "--message", "hi"])
    _t_assert(a.wallet == "w1" and a.message == "hi", "parse sign-message")
    a = ap.parse_args(["sign-tx", "--wallet", "w1", "--tx", "aGVsbG8="])
    _t_assert(a.wallet == "w1" and a.tx == "aGVsbG8=", "parse sign-tx")
    _t_assert(ap.parse_args(["revoke"]).grant_id is None, "parse revoke list")
    _t_assert(
        ap.parse_args(["revoke", "--grant-id", "g1"]).grant_id == "g1",
        "parse revoke --grant-id",
    )
    _t_assert(ap.parse_args(["logout"]).command == "logout", "parse logout")
    _t_assert(ap.parse_args(["selftest"]).command == "selftest", "parse selftest")

    print()
    if _t_assert.failed:
        print("SELFTEST: FAILURES PRESENT")
        sys.exit(1)
    print("SELFTEST: all passed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="privy_device.py",
        description=(
            "Privy OAuth 2.0 Device Authorization Grant — agent/CLI side for "
            "Musebook (Privy app cm7tbyvvy01w2144yss67bjm0). Approve once at "
            "https://musebook.trade/authorize, then transact headlessly. "
            "No app secret required or used."
        ),
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", help="start the device flow and wait for browser approval")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("status", help="show session/token state without printing secrets")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("wallets", help="list the Privy wallets on this grant")
    p.set_defaults(func=cmd_wallets)

    p = sub.add_parser("sign-message", help="sign a message with a Solana embedded wallet")
    p.add_argument("--wallet", required=True, help="Privy wallet id (not the address)")
    p.add_argument("--message", required=True, help="message text to sign (UTF-8)")
    p.set_defaults(func=cmd_sign_message)

    p = sub.add_parser(
        "sign-tx",
        help="sign (never broadcast) a Solana transaction",
    )
    p.add_argument("--wallet", required=True, help="Privy wallet id (not the address)")
    p.add_argument(
        "--tx", required=True, help="base64-encoded serialized Solana transaction"
    )
    p.set_defaults(func=cmd_sign_tx)

    p = sub.add_parser(
        "revoke",
        help="list active agent authorizations, or revoke one by id",
    )
    p.add_argument("--grant-id", default=None, help="revoke this grant id")
    p.set_defaults(func=cmd_revoke)

    p = sub.add_parser("logout", help="delete the stored session")
    p.set_defaults(func=cmd_logout)

    p = sub.add_parser(
        "selftest",
        help="run headless unit tests (no network, no browser needed)",
    )
    p.set_defaults(func=cmd_selftest)
    return ap


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except PrivyError as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        sys.exit("\ninterrupted")


if __name__ == "__main__":
    main()
