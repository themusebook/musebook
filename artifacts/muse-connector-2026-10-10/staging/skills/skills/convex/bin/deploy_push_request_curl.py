"""curl-based variant of deploy_push_request.py — same deploy2 protocol, but uses
curl via subprocess because urllib truncates large responses through the egress
proxy (IncompleteRead). Key handling identical: read via getpass, transient."""

import argparse
import getpass
import json
import subprocess
import sys
import tempfile
import time
import os


def post(base, key, path, payload, timeout=180):
    body = json.dumps(payload).encode()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        f.write(body)
        fname = f.name
    try:
        cmd = [
            "curl", "-sS", "-m", str(timeout),
            "-X", "POST", base + path,
            "-H", "Content-Type: application/json",
            "-H", "Authorization: Convex " + key,
            "-H", "Convex-Client: npm-cli-1.46.0",
            "--data-binary", "@" + fname,
            "-w", "\n%{http_code}",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        out = r.stdout
        code = int(out[out.rfind("\n") + 1:].strip())
        body_text = out[:out.rfind("\n")]
        try:
            return code, json.loads(body_text)
        except Exception:
            return code, body_text[:800]
    finally:
        os.unlink(fname)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--push-request", required=True)
    ap.add_argument("--message", default="")
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
            timeout=120)
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
