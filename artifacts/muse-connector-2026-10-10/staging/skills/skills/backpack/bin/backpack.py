#!/usr/bin/env python3
"""Read-only Backpack Exchange public market-data client.

Uses urllib (respects https_proxy); no auth, no mutations, no credentials.

Usage:
  backpack.py status
  backpack.py markets [--quote USDC]
  backpack.py ticker --symbol SOL_USDC
  backpack.py tickers [--limit 10]
  backpack.py depth --symbol SOL_USDC [--limit 20]
  backpack.py trades --symbol SOL_USDC [--limit 25]
  backpack.py klines --symbol SOL_USDC --interval 1h --hours 24
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.backpack.exchange"
UA = {"User-Agent": "clawd-backpack-skill/1.0"}


def api_get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        if e.code == 429:
            retry = e.headers.get("Retry-After")
            msg = f"Backpack rate-limited (429). Retry-After: {retry}." if retry else \
                "Backpack rate-limited (429). No Retry-After header; wait before retrying."
            raise SystemExit(msg)
        raise SystemExit(f"Backpack HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Network error reaching Backpack: {e.reason}")


def emit(obj):
    print(json.dumps(obj, separators=(",", ":")))


def cmd_status(_):
    emit(api_get("/api/v1/status"))


def cmd_markets(a):
    data = api_get("/api/v1/markets")
    if a.quote:
        q = a.quote.upper()
        data = [m for m in data if str(m.get("quoteAsset", "")).upper() == q]
    emit(data)


def cmd_ticker(a):
    emit(api_get("/api/v1/ticker", {"symbol": a.symbol}))


def cmd_tickers(a):
    data = api_get("/api/v1/tickers")
    if a.limit:
        data = data[:a.limit]
    emit(data)


def cmd_depth(a):
    params = {"symbol": a.symbol}
    if a.limit:
        params["limit"] = a.limit
    emit(api_get("/api/v1/depth", params))


def cmd_trades(a):
    params = {"symbol": a.symbol}
    if a.limit:
        params["limit"] = a.limit
    emit(api_get("/api/v1/trades", params))


def cmd_klines(a):
    # Backpack klines take startTime/endTime in SECONDS (verified live).
    end = int(time.time())
    start = end - int(a.hours * 3600)
    emit(api_get("/api/v1/klines", {
        "symbol": a.symbol,
        "interval": a.interval,
        "startTime": start,
        "endTime": end,
    }))


def main():
    p = argparse.ArgumentParser(description="Read-only Backpack Exchange market data.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="Exchange status")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("markets", help="List markets")
    s.add_argument("--quote", default=None, help="Filter by quote asset, e.g. USDC")
    s.set_defaults(fn=cmd_markets)

    s = sub.add_parser("ticker", help="24h ticker for one symbol")
    s.add_argument("--symbol", required=True, help="e.g. SOL_USDC")
    s.set_defaults(fn=cmd_ticker)

    s = sub.add_parser("tickers", help="All tickers")
    s.add_argument("--limit", type=int, default=None)
    s.set_defaults(fn=cmd_tickers)

    s = sub.add_parser("depth", help="Order book")
    s.add_argument("--symbol", required=True)
    s.add_argument("--limit", type=int, default=None)
    s.set_defaults(fn=cmd_depth)

    s = sub.add_parser("trades", help="Recent trades")
    s.add_argument("--symbol", required=True)
    s.add_argument("--limit", type=int, default=None)
    s.set_defaults(fn=cmd_trades)

    s = sub.add_parser("klines", help="Candles (times are SECONDS)")
    s.add_argument("--symbol", required=True)
    s.add_argument("--interval", default="1h",
                   help="1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M")
    s.add_argument("--hours", type=float, default=24, help="Lookback window in hours")
    s.set_defaults(fn=cmd_klines)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
