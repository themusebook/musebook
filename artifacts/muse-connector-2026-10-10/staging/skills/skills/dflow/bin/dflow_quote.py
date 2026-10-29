#!/usr/bin/env python3
"""DFlow read-only spot quote via the stored custom.dflow connector credential.

Usage: dflow_quote.py <inputMint> <outputMint> <amount_atomic> [--sign] [--watch SEC]
Calls GET /order without userPublicKey (quote-only, no transaction attached).
--sign: request an RFC 9421 signed response (x-sign-request) and verify it
        against DFlow's pinned Ed25519 key. Fails closed on any mismatch.
--watch SEC: poll the quote every SEC seconds, one compact line per poll.
"""
import json
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/skills/dflow/bin")
import dflow_client as C

SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def fetch(in_mint, out_mint, amount, sign):
    headers = {}
    req_id = None
    if sign:
        req_id = C.new_request_id()
        headers = {"x-sign-request": "true", "x-request-id": req_id}
    status, body, resp_headers = C.dflow_get(
        "quote-api.dflow.net", "/order",
        {"inputMint": in_mint, "outputMint": out_mint, "amount": amount},
        extra_headers=headers)
    if status != 200:
        raise RuntimeError("HTTP %d: %s" % (status, body[:200].decode("utf-8", "replace")))
    sig_note = ""
    if sign:
        hdrs = {k.lower(): v for k, v in resp_headers.items()}
        try:
            checks = C.verify_signed_response(status, hdrs, body, req_id)
        except ValueError as e:
            raise RuntimeError("SIGNATURE VERIFICATION FAILED: %s" % e)
        created = checks["freshness"].split("=")[1].split(",")[0]
        sig_note = " sig=verified@%s" % created
    return json.loads(body), sig_note


def show(data, sig_note=""):
    line = ("out=%s impact=%s%% slip=%sbps slot=%s%s" % (
        data.get("outAmount"), data.get("priceImpactPct"),
        data.get("slippageBps"), data.get("contextSlot"), sig_note))
    try:
        line += "  (%.6f SOL -> %.6f USDC)" % (
            int(data["inAmount"]) / 1e9, int(data["outAmount"]) / 1e6)
    except Exception:
        pass
    print(line, flush=True)


def main():
    raw = sys.argv[1:]
    args = []
    skip_next = False
    watch = None
    sign = "--sign" in raw
    for i, a in enumerate(raw):
        if skip_next:
            skip_next = False
            continue
        if a == "--watch":
            watch = float(raw[i + 1])
            skip_next = True
            continue
        if a.startswith("--"):
            continue
        args.append(a)
    if len(args) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    in_mint, out_mint, amount = args
    if watch:
        print("watching every %gs (Ctrl-C to stop)" % watch, flush=True)
        while True:
            try:
                data, note = fetch(in_mint, out_mint, amount, sign)
                show(data, note)
            except RuntimeError as e:
                print("error: %s" % e, file=sys.stderr, flush=True)
            except KeyboardInterrupt:
                break
            time.sleep(watch)
        return 0
    try:
        data, note = fetch(in_mint, out_mint, amount, sign)
    except RuntimeError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    if sign:
        print("signature: VERIFIED (%s)" % note.strip())
    for k in ("inAmount", "outAmount", "otherAmountThreshold", "priceImpactPct",
              "slippageBps", "prioritizationFeeLamports", "contextSlot"):
        if k in data:
            print("%s: %s" % (k, data[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
