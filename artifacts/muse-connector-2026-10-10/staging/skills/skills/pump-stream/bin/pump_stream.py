#!/usr/bin/env python3
"""pump_stream.py — access the pump.musebook.trade token stream.

Two tiers:
  public  — wss://clawd-ws.fly.dev/ws launch feed (no auth; see the
            pumpfun-live skill for the full listener).
  holder  — pump.musebook.trade "Pump + Stonk" stream, gated on any positive
            $CLAWD balance (mint 8cHzQHUS2s2h8TzCmfqPKYiM4dSt4roa3n7MyRLApump).

Holder auth flow (the agent never holds the user's private key):
  1. pump_stream.py challenge --wallet <PUBKEY>
     -> prints challengeId + the exact message to sign.
  2. The user signs the message in their own wallet (Phantom/Solflare/
     Backpack; signMessage, utf8 — NOT a transaction).
  3. pump_stream.py verify --wallet <PUBKEY> --challenge-id <ID> \
        --signature <BASE64_SIG>
     -> stores the session cookie in ~/.pump-stream/session.json (0600).
  4. pump_stream.py tokens [--limit N] | stream [--seconds N]
     -> uses the saved session.

Sessions expire; re-run challenge/verify when you get 401s.
"""
from __future__ import annotations

import argparse
import base64
import http.cookiejar
import json
import os
import sys
import urllib.request

BASE = os.environ.get("PUMP_STREAM_BASE", "https://pump.musebook.trade")
SESSION_FILE = os.path.expanduser("~/.pump-stream/session.json")


class Session:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))
        self._load()

    def _load(self):
        try:
            data = json.load(open(SESSION_FILE))
            for c in data.get("cookies", []):
                ck = http.cookiejar.Cookie(
                    version=0, name=c["name"], value=c["value"],
                    port=None, port_specified=False,
                    domain=c.get("domain", ""), domain_specified=bool(c.get("domain")),
                    domain_initial_dot=False, path=c.get("path", "/"),
                    path_specified=True, secure=c.get("secure", True),
                    expires=None, discard=False, comment=None,
                    comment_url=None, rest={}, rfc2109=False)
                self.jar.set_cookie(ck)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    def save(self):
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        data = {"cookies": [
            {"name": c.name, "value": c.value, "domain": c.domain,
             "path": c.path, "secure": c.secure}
            for c in self.jar]}
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
        os.chmod(SESSION_FILE, 0o600)

    def req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(
            BASE + path, data=data, method=method,
            headers={"Content-Type": "application/json",
                     "User-Agent": "muse-pump-stream/1.0"})
        try:
            with self.opener.open(r, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode())
            except Exception:  # noqa: BLE001
                return e.code, {"error": f"HTTP {e.code}"}


def cmd_policy(_args):
    s = Session()
    code, body = s.req("GET", "/auth/policy")
    print(json.dumps({"http": code, **body}, indent=2))
    return 0 if code == 200 else 1


def cmd_challenge(args):
    s = Session()
    code, body = s.req("POST", "/auth/challenge", {"wallet": args.wallet})
    if code != 200:
        print(json.dumps({"ok": False, "http": code, **body}))
        return 1
    print(json.dumps({
        "ok": True,
        "wallet": args.wallet,
        "challenge_id": body.get("challengeId"),
        "message": body.get("message"),
        "next": "Sign the EXACT message above in the wallet (signMessage, utf8 — not a transaction), "
                "then run: pump_stream.py verify --wallet {} --challenge-id {} --signature <BASE64_SIG>".format(
                    args.wallet, body.get("challengeId")),
    }, indent=2))
    return 0


def cmd_verify(args):
    s = Session()
    code, body = s.req("POST", "/auth/verify", {
        "wallet": args.wallet,
        "challengeId": args.challenge_id,
        "signature": args.signature,
    })
    if code != 200:
        print(json.dumps({"ok": False, "http": code, **body}))
        return 1
    s.save()
    print(json.dumps({"ok": True, "wallet": args.wallet,
                      "session": SESSION_FILE, **body}, indent=2))
    return 0


def _need_auth(code):
    if code == 401:
        print(json.dumps({"ok": False,
                           "error": "session expired or missing — re-run challenge + verify"}))
        return True
    return False


def cmd_tokens(args):
    s = Session()
    code, body = s.req("GET", f"/api/tokens?limit={args.limit}")
    if _need_auth(code):
        return 1
    print(json.dumps({"http": code, "tokens": body if isinstance(body, list) else body},
                     indent=2)[:8000])
    return 0 if code == 200 else 1


def cmd_launches(args):
    s = Session()
    code, body = s.req("GET", f"/api/launches?limit={args.limit}")
    if _need_auth(code):
        return 1
    print(json.dumps({"http": code, "launches": body}, indent=2)[:8000])
    return 0 if code == 200 else 1


def cmd_stream(args):
    import time
    s = Session()
    end = time.time() + args.seconds
    seen = 0
    while time.time() < end:
        code, body = s.req("GET", "/api/stream")
        if _need_auth(code):
            return 1
        if code != 200:
            print(json.dumps({"ok": False, "http": code, **body}))
            return 1
        items = body if isinstance(body, list) else body.get("items", body.get("tokens", []))
        for it in items if isinstance(items, list) else []:
            print(json.dumps(it)[:1000])
            seen += 1
            if args.limit and seen >= args.limit:
                return 0
        time.sleep(args.interval)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="pump.musebook.trade token stream")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("policy", help="show holder-gate policy (no auth)")
    sp.set_defaults(fn=cmd_policy)

    sc = sub.add_parser("challenge", help="get a sign-in challenge for a wallet")
    sc.add_argument("--wallet", required=True)
    sc.set_defaults(fn=cmd_challenge)

    sv = sub.add_parser("verify", help="verify a signed challenge, save session")
    sv.add_argument("--wallet", required=True)
    sv.add_argument("--challenge-id", required=True)
    sv.add_argument("--signature", required=True, help="base64 64-byte signature")
    sv.set_defaults(fn=cmd_verify)

    st = sub.add_parser("tokens", help="latest stream tokens (needs session)")
    st.add_argument("--limit", type=int, default=20)
    st.set_defaults(fn=cmd_tokens)

    sl = sub.add_parser("launches", help="recent launches (needs session)")
    sl.add_argument("--limit", type=int, default=20)
    sl.set_defaults(fn=cmd_launches)

    ss = sub.add_parser("stream", help="poll the live stream (needs session)")
    ss.add_argument("--seconds", type=int, default=60)
    ss.add_argument("--limit", type=int, default=0)
    ss.add_argument("--interval", type=float, default=5.0)
    ss.set_defaults(fn=cmd_stream)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
