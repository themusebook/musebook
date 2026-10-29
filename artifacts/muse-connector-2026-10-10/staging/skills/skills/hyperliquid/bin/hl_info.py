#!/usr/bin/env python3
"""Read-only Hyperliquid perps market data via the keyless public API.

Plain HTTPS POST to https://api.hyperliquid.xyz/info. No auth, no signing,
no wallets. Market data only.

Commands:
  overview [COINS...]        per-coin: mark/oracle/mid, OI (units+notional), funding, prev-day px, 24h vol
  oi [--limit N]             open-interest leaderboard ranked by notional OI
  funding [COINS...]         current + next predicted funding per coin
  mids                       all mark prices
  l2book COIN [--depth N]    L2 book snapshot
  candles COIN INTERVAL [--hours N]   OHLCV candles
  --json                     machine-readable output
"""
import argparse
import json
import subprocess
import sys
import time

BASE = "https://api.hyperliquid.xyz/info"
INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w", "1M"}


def info(payload: dict, retries: int = 4):
    """POST via curl (subprocess) — the egress proxy truncates large
    responses for python's urllib; curl handles them reliably."""
    data = json.dumps(payload)
    last_err = None
    for attempt in range(retries):
        try:
            proc = subprocess.run(
                ["curl", "-s", "-m", "30", "-X", "POST", BASE,
                 "-H", "Content-Type: application/json",
                 "--data-binary", data,
                 "--retry", "2", "--retry-all-errors", "--retry-delay", "2"],
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"curl exit {proc.returncode}: {proc.stderr[:200]}")
            return json.loads(proc.stdout)
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err


def get_ctx():
    meta, ctxs = info({"type": "metaAndAssetCtxs"})
    coins = [u["name"] for u in meta["universe"]]
    return {c: ctx for c, ctx in zip(coins, ctxs)}


def f2(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def overview_rows(coins=None):
    ctx = get_ctx()
    sel = coins if coins else list(ctx.keys())
    rows = []
    for c in sel:
        if c not in ctx:
            continue
        d = ctx[c]
        oi = f2(d["openInterest"])
        mark = f2(d["markPx"])
        rows.append({
            "coin": c,
            "mark_px": mark,
            "oracle_px": f2(d["oraclePx"]),
            "mid_px": f2(d["midPx"]),
            "oi_units": oi,
            "oi_notional": oi * mark,
            "funding": f2(d["funding"]),
            "prev_day_px": f2(d["prevDayPx"]),
            "day_ntl_vlm": f2(d["dayNtlVlm"]),
            "day_base_vlm": f2(d["dayBaseVlm"]),
        })
    return rows


def cmd_overview(args):
    rows = overview_rows(args.coins)
    if args.json:
        return rows
    hdr = f"{'COIN':<8}{'MARK':>12}{'MID':>12}{'OI(units)':>14}{'OI(notional)':>15}{'FUNDING':>11}{'24H NTL VOL':>14}"
    lines = [hdr]
    for r in rows:
        lines.append(f"{r['coin']:<8}{r['mark_px']:>12.4g}{r['mid_px']:>12.4g}"
                     f"{r['oi_units']:>14.4g}{r['oi_notional']:>15.3g}"
                     f"{r['funding']:>11.7f}{r['day_ntl_vlm']:>14.3g}")
    return "\n".join(lines)


def cmd_oi(args):
    rows = sorted(overview_rows(), key=lambda r: r["oi_notional"], reverse=True)[: args.limit]
    if args.json:
        return rows
    lines = [f"{'RANK':<6}{'COIN':<8}{'OI(notional)':>14}{'OI(units)':>14}{'MARK':>12}"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i:<6}{r['coin']:<8}{r['oi_notional']:>14.3g}"
                     f"{r['oi_units']:>14.4g}{r['mark_px']:>12.4g}")
    return "\n".join(lines)


def cmd_funding(args):
    cur = get_ctx()
    pred = info({"type": "predictedFundings"})
    want = set(args.coins) if args.coins else None
    rows = []
    for coin, venues in pred:
        if want and coin not in want:
            continue
        hl = next((v[1] for v in venues if v[0] == "HlPerp"), None)
        if hl is None:
            continue
        nxt = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(hl["nextFundingTime"] / 1000))
        rows.append({
            "coin": coin,
            "funding_now": f2(cur[coin]["funding"]) if coin in cur else None,
            "funding_next": f2(hl["fundingRate"]),
            "next_funding_at": nxt,
            "interval_hours": hl["fundingIntervalHours"],
        })
    if args.json:
        return rows
    lines = [f"{'COIN':<8}{'FUND NOW':>12}{'FUND NEXT':>12}{'NEXT AT':>20}"]
    for r in rows:
        fn = r["funding_now"]
        lines.append(f"{r['coin']:<8}{fn if fn is not None else '-':>12}"
                     f"{r['funding_next']:>12.7f} {r['next_funding_at']:>20}")
    return "\n".join(lines)


def cmd_mids(args):
    mids = info({"type": "allMids"})
    if args.json:
        return mids
    rows = sorted(mids.items(), key=lambda kv: f2(kv[1]), reverse=True)
    return "\n".join(f"{k:<8}{f2(v):>12.4g}" for k, v in rows)


def cmd_l2book(args):
    d = info({"type": "l2Book", "coin": args.coin})
    if args.json:
        return d
    bids, asks = d["levels"]
    lines = [f"{args.coin} L2 book @ {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(d['time']/1000))}",
             f"{'BID':<12}{'SZ':>10}   {'ASK':<12}{'SZ':>10}"]
    for i in range(min(args.depth, len(bids), len(asks))):
        b, a = bids[i], asks[i]
        lines.append(f"{b['px']:<12}{float(b['sz']):>10.4f}   {a['px']:<12}{float(a['sz']):>10.4f}")
    return "\n".join(lines)


def cmd_candles(args):
    now = int(time.time() * 1000)
    hours = args.hours or 24
    d = info({"type": "candleSnapshot",
              "req": {"coin": args.coin, "interval": args.interval,
                      "startTime": now - hours * 3600 * 1000, "endTime": now}})
    if args.json:
        return d
    lines = [f"{'T(UTC)':<18}{'OPEN':>10}{'HIGH':>10}{'LOW':>10}{'CLOSE':>10}{'VOL':>12}"]
    for c in d:
        t = time.strftime("%m-%d %H:%M", time.gmtime(c["t"] / 1000))
        lines.append(f"{t:<18}{float(c['o']):>10.4g}{float(c['h']):>10.4g}"
                     f"{float(c['l']):>10.4g}{float(c['c']):>10.4g}{float(c['v']):>12.4g}")
    return "\n".join(lines)


def main():
    argv = sys.argv[1:]
    json_out = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    p = argparse.ArgumentParser(description="Read-only Hyperliquid perps market data")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("overview"); s.add_argument("coins", nargs="*")
    s = sub.add_parser("oi"); s.add_argument("--limit", type=int, default=20)
    s = sub.add_parser("funding"); s.add_argument("coins", nargs="*")
    sub.add_parser("mids")
    s = sub.add_parser("l2book"); s.add_argument("coin"); s.add_argument("--depth", type=int, default=10)
    s = sub.add_parser("candles"); s.add_argument("coin"); s.add_argument("interval", choices=sorted(INTERVALS)); s.add_argument("--hours", type=int)

    args = p.parse_args(argv)
    args.json = json_out
    out = {"overview": cmd_overview, "oi": cmd_oi, "funding": cmd_funding,
           "mids": cmd_mids, "l2book": cmd_l2book, "candles": cmd_candles}[args.cmd](args)
    print(json.dumps(out, indent=2) if json_out else out)


if __name__ == "__main__":
    main()
