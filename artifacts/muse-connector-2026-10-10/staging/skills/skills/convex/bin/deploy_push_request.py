"""Convex code deploy for when the stored surrogate cannot satisfy the deploy2 protocol.

BACKGROUND (proven 2026-09-19, do not re-investigate):
- The `custom.convex` secure credential has placement {"custom_header": "Authorization"}:
  Sentinel/authd injects the real key ONLY into the Authorization header, and
  ONLY for the exact process that obtained the surrogate. Child processes,
  node, and JSON bodies are never swapped.
- Convex's deploy2 protocol (POST /api/deploy2/start_push, /wait_for_schema,
  /finish_push) REQUIRES adminKey as a JSON body field and ignores the
  Authorization header. Therefore `npx convex deploy` can never authenticate
  with the stored surrogate, in any process, with any header/body combination.
- A vault reconnect cannot fix this: no placement puts the key in a JSON body.

WORKING FLOW (needs the raw deploy key, used transiently, never stored):
  1. node (local, no auth needed) bundles and dumps the push request:
       ./node_modules/.bin/convex deploy --url <DEPLOY_URL> --admin-key placeholder \\
           --yes --skip-workos-check --push-all-modules \\
           --write-push-request /tmp/pushreq --typecheck disable
     This writes /tmp/pushreq.json and exits BEFORE any network call.
  2. This script POSTs start_push -> wait_for_schema -> finish_push with the
     real key in both the Authorization header and the JSON body.

USAGE:
    python3 deploy_push_request.py --url https://<deployment>.convex.cloud \\
        --push-request /tmp/pushreq.json
  The deploy key is read via getpass (never from argv/env/files/history).
"""

import argparse
import brotli
import getpass
import json
import sys
import time
import urllib.request
import urllib.error

PLACEHOLDER = "via-authorization-header"  # unused when a real key is supplied


def post(base, key, path, payload, compress=True, timeout=180):
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Convex " + key,
        "Convex-Client": "npm-cli-1.46.0",
    }
    if compress:
        body = brotli.compress(body, mode=brotli.MODE_TEXT, quality=4)
        headers["Content-Encoding"] = "br"
    req = urllib.request.Request(base + path, data=body, headers=headers, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:800]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Deployment URL, e.g. https://xxx.convex.cloud")
    ap.add_argument("--push-request", required=True, help="Path to pushreq.json from --write-push-request")
    ap.add_argument("--message", default="", help="Deploy message recorded server-side")
    args = ap.parse_args()

    key = getpass.getpass("Convex deploy key (transient, never stored): ").strip()
    if not key:
        sys.exit("no key supplied")

    push_req = json.load(open(args.push_request))
    push_req["adminKey"] = key

    st, start_resp = post(args.url, key, "/api/deploy2/start_push", push_req)
    print("start_push ->", st, flush=True)
    if st != 200:
        print(start_resp)
        sys.exit(1)

    for attempt in range(30):
        st, ws = post(
            args.url, key, "/api/deploy2/wait_for_schema",
            {"adminKey": key, "schemaChange": start_resp["schemaChange"],
             "timeoutMs": 60000, "dryRun": False},
            compress=False, timeout=120)
        if st != 200:
            print("wait_for_schema ->", st, ws)
            sys.exit(1)
        t = ws.get("type")
        print(f"  schema [{attempt}]:", t, flush=True)
        if t == "complete":
            break
        if t == "failed":
            print("SCHEMA FAILED:", ws)
            sys.exit(1)
        time.sleep(2)
    else:
        sys.exit("schema wait timed out")

    st, fin = post(
        args.url, key, "/api/deploy2/finish_push",
        {"adminKey": key, "startPush": start_resp, "dryRun": False,
         "message": args.message or None})
    print("finish_push ->", st, flush=True)
    if st != 200:
        print(fin)
        sys.exit(1)
    print("DEPLOY OK")


if __name__ == "__main__":
    main()
