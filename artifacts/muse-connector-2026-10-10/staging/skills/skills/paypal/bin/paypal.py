#!/usr/bin/env python3
"""PayPal REST API client.

Auth model: PayPal needs a client ID + client secret pair, exchanged for a
short-lived OAuth2 Bearer token (POST /v1/oauth2/token, Basic auth,
grant_type=client_credentials). The pair is NEVER stored by the agent. It is
read at runtime from, in order:

  1. env vars  PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET
  2. file      ~/.config/paypal/credentials   (KEY=VALUE lines, mode 0600)

The Bearer token is cached at ~/.cache/paypal/token_<env>.json (0600) with an
expiry timestamp and refreshed automatically. Secrets and tokens are never
printed or logged; commands only report metadata (app_id, scope, expiry).

Usage:
  paypal.py token [--env live|sandbox] [--force]
  paypal.py call [--env live|sandbox] METHOD /v2/path [--data '{"k":"v"}']
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

HOSTS = {"live": "api-m.paypal.com", "sandbox": "api-m.sandbox.paypal.com"}
CONFIG_FILE = os.path.expanduser("~/.config/paypal/credentials")
CACHE_DIR = os.path.expanduser("~/.cache/paypal")


def load_secrets():
    cid = os.environ.get("PAYPAL_CLIENT_ID")
    csec = os.environ.get("PAYPAL_CLIENT_SECRET")
    if cid and csec:
        return cid, csec
    if os.path.exists(CONFIG_FILE):
        vals = {}
        with open(CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip().strip('"').strip("'")
        if vals.get("PAYPAL_CLIENT_ID") and vals.get("PAYPAL_CLIENT_SECRET"):
            return vals["PAYPAL_CLIENT_ID"], vals["PAYPAL_CLIENT_SECRET"]
    return None, None


def _cache_path(env):
    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
    return os.path.join(CACHE_DIR, "token_%s.json" % env)


def _exchange(env, cid, csec):
    basic = base64.b64encode(("%s:%s" % (cid, csec)).encode()).decode()
    req = urllib.request.Request(
        "https://%s/v1/oauth2/token" % HOSTS[env],
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        print("token exchange failed: HTTP %s %s" % (e.code, detail), file=sys.stderr)
        sys.exit(1)
    tok = {
        "token_type": body.get("token_type", "Bearer"),
        "scope": body.get("scope", ""),
        "app_id": body.get("app_id", ""),
        "expires_at": time.time() + int(body.get("expires_in", 30000)) - 120,
        "access_token": body["access_token"],
    }
    cp = _cache_path(env)
    tmp = cp + ".tmp"
    with open(tmp, "w") as f:
        json.dump(tok, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, cp)
    return tok


def get_token(env, force=False):
    cp = _cache_path(env)
    if not force and os.path.exists(cp):
        try:
            with open(cp) as f:
                tok = json.load(f)
            if tok.get("expires_at", 0) > time.time() + 30 and tok.get("access_token"):
                return tok
        except Exception:
            pass
    cid, csec = load_secrets()
    if not cid or not csec:
        print("missing credentials: set PAYPAL_CLIENT_ID/PAYPAL_CLIENT_SECRET "
              "or create ~/.config/paypal/credentials", file=sys.stderr)
        sys.exit(2)
    return _exchange(env, cid, csec)


def cmd_token(args):
    tok = get_token(args.env, force=args.force)
    print(json.dumps({
        "env": args.env,
        "host": HOSTS[args.env],
        "app_id": tok.get("app_id"),
        "token_type": tok.get("token_type"),
        "scope": tok.get("scope"),
        "expires_in_seconds": max(0, int(tok.get("expires_at", 0) - time.time())),
    }, indent=2))


def _api_call(env, method, path, data=None, _retried=False):
    tok = get_token(env)
    headers = {
        "Authorization": "%s %s" % (tok.get("token_type", "Bearer"), tok["access_token"]),
        "Accept": "application/json",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request("https://%s%s" % (HOSTS[env], path),
                                 data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        if e.code == 401 and not _retried:
            get_token(env, force=True)  # refresh once, then retry
            return _api_call(env, method, path, data, _retried=True)
        detail = e.read().decode()[:500]
        print("API call failed: HTTP %s %s" % (e.code, detail), file=sys.stderr)
        sys.exit(1)


def cmd_call(args):
    data = json.loads(args.data) if args.data else None
    status, body = _api_call(args.env, args.method, args.path, data)
    print(json.dumps({"http_status": status, "response": body}, indent=2)[:4000])


def main():
    p = argparse.ArgumentParser(description="PayPal REST API client")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("token", help="exchange credentials for an access token (reports metadata only)")
    t.add_argument("--env", choices=["live", "sandbox"], default="live")
    t.add_argument("--force", action="store_true", help="ignore cache, fetch a fresh token")
    t.set_defaults(fn=cmd_token)

    c = sub.add_parser("call", help="call a PayPal REST endpoint")
    c.add_argument("--env", choices=["live", "sandbox"], default="live")
    c.add_argument("method", help="HTTP method, e.g. GET")
    c.add_argument("path", help="API path, e.g. /v2/invoicing/invoices?page_size=1")
    c.add_argument("--data", help="JSON request body for POST/PUT/PATCH")
    c.set_defaults(fn=cmd_call)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
