#!/usr/bin/env python3
"""Shared DFlow REST client: connector-surrogate auth + RFC 9421 signed-response verification.

Read-only. Never prints the raw API key; only the surrogate reference is used.
"""
import base64
import hashlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
import dynamic_credentials as dc

CRED = "custom.dflow"
ALLOWED = ("quote-api.dflow.net", "d.prediction-markets-api.dflow.net", "pond.dflow.net")

# DFlow's published Ed25519 public key for HTTP Message Signatures (RFC 9421).
DFLOW_PUBKEY_B58 = "EZKxYr7bbXHaKAGw2MEpVUU9He3hwXGejSpCsdsZCmiF"


def _b58decode(s):
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for ch in s:
        n = n * 58 + alphabet.index(ch)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + raw


def dflow_get(host, path, params=None, extra_headers=None, timeout=60):
    """GET via the connector surrogate. Returns (status, raw_body, headers_dict)."""
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"https://{host}{path}{qs}"
    req = urllib.request.Request(url, method="GET")
    dc.add_surrogate_to_request(req, CRED, allowed_hosts=ALLOWED)
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def new_request_id():
    return uuid.uuid4().hex


# ---- RFC 9421 verification -------------------------------------------------

_SF_PARAM = re.compile(r""";\s*([a-zA-Z][a-zA-Z0-9_\-]*)\s*=\s*("(?:[^"\\]|\\.)*"|[^\s;,)]+)""")


_SF_ITEM = re.compile(r'''"([^"]+)"((?:\s*;\s*[A-Za-z][\w\-]*(?:\s*=\s*(?:"[^"]*"|[^\s;,)]+))?)*)''')


def _canonical_component_id(item_match):
    """Serialize a covered component identifier per RFC 9421, keeping item params.

    E.g. '"x-request-id";req' -> '"x-request-id";req' (the ;req is part of the
    component id and appears in the signature base line).
    """
    name, rest = item_match.group(1).lower(), item_match.group(2)
    out = [f'"{name}"']
    for pm in re.finditer(r';\s*([A-Za-z][\w\-]*)\s*(=\s*("[^"]*"|[^\s;,)]+))?', rest):
        k, eqv = pm.group(1), pm.group(3)
        out.append(f";{k}" if eqv is None else f";{k}={eqv.strip()}")
    return "".join(out)


def _parse_signature_input(value, label="sig1"):
    """Parse `label=(...components...);created=..;keyid="..";alg=".."`.

    Returns (covered_components, params_dict, inner_list_with_params_verbatim).
    covered_components is a list of (bare_name, canonical_id) tuples.
    """
    m = re.search(re.escape(label) + r"\s*=\s*\(", value)
    if not m:
        raise ValueError(f"label {label} not found in signature-input")
    start = m.end() - 1
    depth = 0
    end = None
    for i in range(start, len(value)):
        if value[i] == "(":
            depth += 1
        elif value[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise ValueError("unbalanced inner list in signature-input")
    inner = value[start:end + 1]
    # Parameters belonging to this signature run from just after the inner
    # list to the next top-level comma (another signature) or end of header.
    rest = value[end + 1:]
    depth = 0
    cut = len(rest)
    for i, ch in enumerate(rest):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            cut = i
            break
    inner_with_params = inner + rest[:cut].rstrip()
    params = {}
    for pm in _SF_PARAM.finditer(rest[:cut]):
        k, v = pm.group(1), pm.group(2)
        if v.startswith('"'):
            v = v[1:-1]
        params[k] = v
    components = []
    for im in _SF_ITEM.finditer(inner):
        components.append((im.group(1).lower(), _canonical_component_id(im)))
    return components, params, inner_with_params


def _component_line(bare_name, canonical_id, status, headers):
    if bare_name == "@status":
        return f'{canonical_id}: {status}'
    if bare_name == "@method":
        return f'{canonical_id}: GET'
    if bare_name == "@authority":
        return f'{canonical_id}: {headers.get("host", "")}'.lower()
    val = headers.get(bare_name)
    if val is None:
        raise ValueError(f"covered component {bare_name} missing from response headers")
    return f'{canonical_id}: {val.strip()}'


def verify_signed_response(status, headers, body, expected_request_id,
                           pubkey_b58=DFLOW_PUBKEY_B58, max_age_s=300):
    """Fail-closed verification of a DFlow RFC 9421 signed response.

    Returns a dict of the checks performed. Raises ValueError on any failure.
    """
    checks = {}
    sig_input = headers.get("signature-input")
    signature = headers.get("signature")
    digest = headers.get("content-digest")
    resp_req_id = headers.get("x-request-id")
    if not sig_input:
        raise ValueError("missing signature-input header")
    if not signature:
        raise ValueError("missing signature header")
    if not digest:
        raise ValueError("missing content-digest header")
    if not resp_req_id:
        raise ValueError("missing x-request-id response header")

    # 1. request id binding
    if resp_req_id != expected_request_id:
        raise ValueError("x-request-id mismatch (possible replay)")
    checks["request_id"] = "match"

    # 2. content-digest over the exact raw body
    dm = re.match(r'([a-z0-9\-]+)=:([A-Za-z0-9+/=]+):', digest.strip())
    if not dm:
        raise ValueError("unparseable content-digest header")
    alg, want = dm.group(1), dm.group(2)
    h = {"sha-256": hashlib.sha256, "sha-512": hashlib.sha512}.get(alg)
    if h is None:
        raise ValueError(f"unsupported digest algorithm {alg}")
    got = base64.b64encode(h(body).digest()).decode()
    if got != want:
        raise ValueError("content-digest mismatch: body does not match digest")
    checks["content_digest"] = f"{alg}:match"

    # 3. parse signature-input
    sm = re.search(r"([A-Za-z0-9_\-]+)\s*=:\s*([A-Za-z0-9+/=]+)\s*:", signature.strip())
    if not sm:
        raise ValueError("unparseable signature header")
    label, sig_b64 = sm.group(1), sm.group(2)
    components, params, inner_verbatim = _parse_signature_input(sig_input, label)

    # 4. key id must be DFlow's pinned key
    keyid = params.get("keyid")
    if keyid != pubkey_b58:
        raise ValueError(f"unexpected keyid {keyid!r}")
    checks["keyid"] = "pinned-dflow-key"
    if params.get("alg", "ed25519") != "ed25519":
        raise ValueError(f"unexpected alg {params.get('alg')!r}")

    # 5. freshness
    created = int(params.get("created", "0"))
    now = int(time.time())
    if abs(now - created) > max_age_s:
        raise ValueError(f"signature created={created} outside freshness window")
    checks["freshness"] = f"created={created}, skew_ok"

    # 6. rebuild signature base and verify
    hdrs = {k.lower(): v for k, v in headers.items()}
    lines = [_component_line(bare, canon, status, hdrs) for bare, canon in components]
    lines.append(f'"@signature-params": {inner_verbatim}')
    sig_base = "\n".join(lines).encode("utf-8")
    sig = base64.b64decode(sig_b64)
    pubkey = _b58decode(pubkey_b58)
    try:
        from nacl.bindings import crypto_sign_open
    except ImportError:
        raise ValueError("PyNaCl not installed; cannot verify ed25519")
    try:
        # crypto_sign_open verifies a combined (sig || msg); detached verify
        # is equivalent to opening the concatenation.
        recovered = crypto_sign_open(sig + sig_base, pubkey)
        if recovered != sig_base:
            raise ValueError("ed25519 signature verification failed")
    except Exception as e:
        raise ValueError(f"ed25519 signature verification failed: {type(e).__name__}")
    checks["ed25519"] = "valid"
    checks["covered"] = ",".join(canon for _, canon in components)
    return checks
