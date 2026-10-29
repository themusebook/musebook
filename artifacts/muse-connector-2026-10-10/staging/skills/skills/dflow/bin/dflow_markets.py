#!/usr/bin/env python3
"""DFlow prediction-markets metadata via the stored custom.dflow credential.

Read-only. Uses GET /api/v1/markets on d.prediction-markets-api.dflow.net.

Usage:
  dflow_markets.py list [--status active] [--search TEXT] [--limit N] [--cursor C]
  dflow_markets.py show <TICKER>

Prices are decimal fractions of $1 (e.g. yesBid 0.62 = 62c).
"""
import datetime
import json
import sys

sys.path.insert(0, "/home/hatch/workspace/skills/dflow/bin")
import dflow_client as C

HOST = "d.prediction-markets-api.dflow.net"


def fmt_ts(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return "?"


def brief(m):
    bid, ask = m.get("yesBid"), m.get("yesAsk")
    px = f"{float(bid)*100:4.1f}c/{float(ask)*100:4.1f}c" if bid and ask else "no quote"
    return (f"{m['ticker']} [{m['status']}] {px} "
            f"vol24h=${float(m.get('volume24hFp') or 0):,.0f} "
            f"close={fmt_ts(m.get('closeTime'))} :: {m['title'][:80]}")


def cmd_list(argv):
    params = {"limit": "20"}
    i = 0
    while i < len(argv):
        if argv[i] == "--status" and i + 1 < len(argv):
            params["status"] = argv[i + 1]; i += 2
        elif argv[i] == "--search" and i + 1 < len(argv):
            params["search"] = argv[i + 1]; i += 2
        elif argv[i] == "--limit" and i + 1 < len(argv):
            params["limit"] = argv[i + 1]; i += 2
        elif argv[i] == "--cursor" and i + 1 < len(argv):
            params["cursor"] = argv[i + 1]; i += 2
        else:
            i += 1
    status, body, _ = C.dflow_get(HOST, "/api/v1/markets", params)
    if status != 200:
        print(f"HTTP {status}: {body[:200].decode('utf-8','replace')}", file=sys.stderr)
        return 1
    data = json.loads(body)
    ms = data.get("markets", [])
    for m in ms:
        print(brief(m))
    print(f"--- {len(ms)} markets, cursor={data.get('cursor')}")
    return 0


def cmd_show(argv):
    if not argv:
        print("usage: dflow_markets.py show <TICKER>", file=sys.stderr)
        return 2
    ticker = argv[0].strip().upper()
    # No single-ticker endpoint and `search` is ignored server-side, so scan
    # pages via cursor (read-only; capped).
    cursor = None
    found = None
    for _ in range(15):
        params = {"limit": "100"}
        if cursor:
            params["cursor"] = cursor
        status, body, _ = C.dflow_get(HOST, "/api/v1/markets", params)
        if status != 200:
            print(f"HTTP {status}: {body[:200].decode('utf-8','replace')}", file=sys.stderr)
            return 1
        data = json.loads(body)
        ms = data.get("markets", [])
        if not ms:
            break
        for m in ms:
            if m["ticker"].upper() == ticker:
                found = m
                break
        if found:
            break
        cursor = data.get("cursor")
        if not cursor:
            break
    if not found:
        print(f"no market with ticker {ticker} in scanned pages", file=sys.stderr)
        return 1
    m = found
    print(f"ticker:   {m['ticker']}")
    print(f"title:    {m['title']}")
    print(f"status:   {m['status']}" + (f" (result: {m['result']})" if m.get("result") else ""))
    print(f"event:    {m['eventTicker']}  type={m['marketType']}")
    bid, ask = m.get("yesBid"), m.get("yesAsk")
    if bid and ask:
        print(f"yes:      bid {float(bid)*100:.1f}c  ask {float(ask)*100:.1f}c")
    nbid, nask = m.get("noBid"), m.get("noAsk")
    if nbid and nask:
        print(f"no:       bid {float(nbid)*100:.1f}c  ask {float(nask)*100:.1f}c")
    print(f"volume24h: ${float(m.get('volume24hFp') or 0):,.2f}")
    print(f"openInterest: ${float(m.get('openInterestFp') or 0):,.2f}")
    print(f"close:    {fmt_ts(m.get('closeTime'))}")
    for mint, acct in (m.get("accounts") or {}).items():
        print(f"rail {mint[:8]}...: yesMint={acct['yesMint']} noMint={acct['noMint']} "
              f"init={acct['isInitialized']} redeem={acct['redemptionStatus']}")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "show"):
        print(__doc__, file=sys.stderr)
        return 2
    if sys.argv[1] == "list":
        return cmd_list(sys.argv[2:])
    return cmd_show(sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
