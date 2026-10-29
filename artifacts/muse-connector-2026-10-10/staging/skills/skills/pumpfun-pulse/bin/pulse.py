#!/usr/bin/env python3
"""PumpFun Pulse: collect recent pump.fun launches, enrich via BirdEye
(meme/detail/single + token_overview per mint, token_trending for the
trending block), score them, and emit a ranked digest.

Tape window is 30m (BirdEye's finest per-interval bucket is 1m/5m/30m;
there is no 15m bucket, so 30m is used honestly instead of interpolating).

Usage:
  pulse.py [--window-min 20] [--max-enrich 12] [--top 6] [--json-only]
  pulse.py --build-live OUT_JSON [--live-count 12]

Auth: reuses ~/workspace/skills/birdeye/bin/birdeye.py (stored
custom.birdeye credential via surrogate exchange). Never paste or print
raw API keys.

Discovery: the local launch logger's all_launches.jsonl (real creation
timestamps, zero API calls). Falls back to BirdEye meme/list sorted by
last trade time if the log is missing or stale.

Note: token_security and token_creation_info are NOT on this BirdEye
plan (401 insufficient permissions), so authority/rug fields are
unavailable here. Pre-trade authority diligence stays with the rug-check
skill; graduated tokens are flagged (they trade on AMM, not the curve).
"""
import argparse
import datetime as dt
import json
import math
import os
import subprocess
import sys
import time

BE = "/home/hatch/workspace/skills/birdeye/bin/birdeye.py"
LAUNCH_LOG = "/home/hatch/workspace/goals/pump-fun-launch-pulse/hidden_files/all_launches.jsonl"
CHAIN_HEADER = ["--header", "x-chain: solana"]
CALL_DELAY = 1.2  # polite pacing: BirdEye rate-limits aggressively


def be_call(path, retries=3):
    """GET a BirdEye path via the birdeye CLI. Returns parsed JSON dict."""
    last = {"ok": False, "error": "no attempt"}
    for attempt in range(retries):
        cmd = [BE, "GET", path] + CHAIN_HEADER
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            payload = json.loads(out.stdout.strip() or "{}")
        except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            payload = {"ok": False, "error": f"cli: {type(e).__name__}"}
        err = str(payload.get("error", ""))
        # BirdEye returns HTTP 400 (not 429) for CU-cap errors; retry both.
        if payload.get("ok") is False and ("429" in err or "Compute units" in err) \
                and attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
            continue
        last = payload
        break
    time.sleep(CALL_DELAY)
    return last


def be_data(payload):
    if not isinstance(payload, dict):
        return None
    if payload.get("ok") is False:
        return None
    data = payload.get("data")
    if isinstance(data, dict) and data.get("success") is False:
        return None
    return data


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def to_epoch_sec(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v / 1000.0 if v > 1e12 else float(v)
    if isinstance(v, str):
        s = v.strip()
        if s.isdigit():
            return to_epoch_sec(int(s))
        try:
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def discover_from_log(window_min):
    """Fresh launches from the local launch logger (real creation ts)."""
    if not os.path.exists(LAUNCH_LOG):
        return None
    if time.time() - os.path.getmtime(LAUNCH_LOG) > 15 * 60:
        return None  # stale log; fall back to BirdEye discovery
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - window_min * 60
    seen = {}
    try:
        with open(LAUNCH_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    it = json.loads(line)
                except json.JSONDecodeError:
                    continue
                mint = it.get("mint")
                ts = to_epoch_sec(it.get("ts"))
                if not mint or not ts or ts < cutoff:
                    continue
                if mint not in seen or ts < seen[mint]["created_at"]:
                    links = it.get("links") or {}
                    seen[mint] = {
                        "mint": mint,
                        "name": it.get("name") or "?",
                        "symbol": it.get("symbol") or "?",
                        "created_at": ts,
                        "twitter": bool(links.get("twitter")),
                        "telegram": bool(links.get("telegram")),
                        "website": bool(links.get("website")),
                    }
    except OSError:
        return None
    fresh = sorted(seen.values(), key=lambda x: x["created_at"], reverse=True)
    return fresh


def discover_from_birdeye(window_min, limit=50):
    """Fallback discovery: BirdEye meme list by most recent trade."""
    payload = be_call(f"/defi/v3/token/meme/list?sort_by=last_trade_unix_time"
                      f"&sort_type=desc&limit={limit}")
    data = be_data(payload)
    items = (data or {}).get("items", []) if isinstance(data, dict) else []
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - window_min * 60
    fresh = []
    for it in items:
        lt = num(it.get("last_trade_unix_time"))
        if lt < cutoff:
            continue
        ext = it.get("extensions") or {}
        fresh.append({
            "mint": it.get("address") or "?",
            "name": it.get("name") or "?",
            "symbol": it.get("symbol") or "?",
            "created_at": lt,  # last-trade proxy; true creation unknown here
            "twitter": bool(ext.get("twitter")),
            "telegram": bool(ext.get("telegram")),
            "website": bool(ext.get("website")),
        })
    return fresh


def enrich(mint):
    """BirdEye enrichment for one mint: meme detail + token overview."""
    c = {"mint": mint}
    detail = be_data(be_call(f"/defi/v3/token/meme/detail/single?address={mint}"))
    if isinstance(detail, dict):
        mi = detail.get("meme_info") or {}
        ext = detail.get("extensions") or {}
        c.update({
            "name": detail.get("name") or "?",
            "symbol": detail.get("symbol") or "?",
            "price_usd": num(detail.get("price")),
            "mcap_usd": num(detail.get("market_cap") or detail.get("fdv")),
            "liquidity_usd": num(detail.get("liquidity")),
            "created_at": to_epoch_sec(mi.get("created_at") or mi.get("creation_time")),
            "creator": mi.get("creator"),
            "progress_percent": num(mi.get("progress_percent")),
            "graduated": bool(mi.get("graduated")),
            "twitter": bool(ext.get("twitter")),
            "telegram": bool(ext.get("telegram")),
            "website": bool(ext.get("website")),
            "image": detail.get("logo_uri") or "",
        })
    ov = be_data(be_call(f"/defi/token_overview?address={mint}"))
    if isinstance(ov, dict):
        if not c.get("price_usd"):
            c["price_usd"] = num(ov.get("price"))
        if not c.get("mcap_usd"):
            c["mcap_usd"] = num(ov.get("marketCap"))
        if not c.get("liquidity_usd"):
            c["liquidity_usd"] = num(ov.get("liquidity"))
        if c.get("name") in (None, "?") and ov.get("name"):
            c["name"] = ov.get("name")
        if c.get("symbol") in (None, "?") and ov.get("symbol"):
            c["symbol"] = ov.get("symbol")
        ext = ov.get("extensions") or {}
        if not c.get("twitter"):
            c["twitter"] = bool(ext.get("twitter"))
        if not c.get("website"):
            c["website"] = bool(ext.get("website"))
        c.update({
            "holders": int(num(ov.get("holder"))),
            "txns": int(num(ov.get("trade30m"))),
            "buys": int(num(ov.get("buy30m"))),
            "sells": int(num(ov.get("sell30m"))),
            "volume_30m": num(ov.get("vBuy30mUSD")) + num(ov.get("vSell30mUSD")),
            "volume_30m_buys": num(ov.get("vBuy30mUSD")),
            "volume_30m_sells": num(ov.get("vSell30mUSD")),
            "wallets_30m": int(num(ov.get("uniqueWallet30m"))),
            "price_change_30m_pct": num(ov.get("priceChange30mPercent")),
        })
    return c


def score(c):
    """Transparent momentum score (30m BirdEye tape). Returns (score, reasons, flags)."""
    reasons, flags = [], []
    s = 0.0
    v = c.get("volume_30m", 0)
    s += 2.0 * math.log10(v + 1)
    if v > 0:
        reasons.append(f"30m vol ${v:,.0f}")
    t = c.get("txns", 0)
    s += math.log10(t + 1)
    if t > 50:
        reasons.append(f"{t} txns")
    h = c.get("holders", 0)
    s += 1.5 * math.log10(h + 1)
    if h > 50:
        reasons.append(f"{h} holders")
    buys, sells = c.get("buys", 0), c.get("sells", 0)
    if buys + sells > 10:
        ratio = buys / (buys + sells)
        s += 2.0 * (ratio - 0.5)
        if ratio > 0.6:
            reasons.append(f"{ratio:.0%} buys")
    pc = c.get("price_change_30m_pct", 0)
    if pc > 20:
        s += 1.0
        reasons.append(f"+{pc:.0f}% 30m")
    elif pc < -30:
        s -= 1.0
        flags.append(f"{pc:.0f}% 30m")
    if c.get("twitter"):
        s += 1.0
        reasons.append("twitter")
    if c.get("telegram"):
        s += 1.0
        reasons.append("telegram")
    if c.get("website"):
        s += 0.5
    pp = c.get("progress_percent", 0)
    if c.get("graduated"):
        s -= 1.0
        flags.append("graduated (AMM)")
    elif pp >= 80:
        s += 1.0
        reasons.append(f"{pp:.0f}% to graduation")
    return round(s, 2), reasons, flags


def summarize(c):
    sc, reasons, flags = score(c)
    return {
        "name": (c.get("name", "?") or "?").strip() or "?",
        "symbol": (c.get("symbol", "?") or "?").strip() or "?",
        "mint": c.get("mint", "?"),
        "score": sc,
        "price_usd": c.get("price_usd", 0), "mcap_usd": c.get("mcap_usd", 0),
        "liquidity_usd": c.get("liquidity_usd", 0),
        "volume_30m": c.get("volume_30m", 0),
        "volume_30m_buys": c.get("volume_30m_buys", 0),
        "volume_30m_sells": c.get("volume_30m_sells", 0),
        "price_change_30m_pct": c.get("price_change_30m_pct", 0),
        "holders": c.get("holders", 0), "txns": c.get("txns", 0),
        "buys": c.get("buys", 0), "sells": c.get("sells", 0),
        "wallets_30m": c.get("wallets_30m", 0),
        "progress_percent": c.get("progress_percent", 0),
        "graduated": c.get("graduated", False),
        "creator": c.get("creator"),
        "created_at": c.get("created_at"),
        "reasons": reasons, "flags": flags,
        "links": {
            "twitter": c.get("twitter", False), "telegram": c.get("telegram", False),
            "website": c.get("website", False),
            "pumpfun": f"https://pump.fun/coin/{c.get('mint')}",
            "solscan": f"https://solscan.io/token/{c.get('mint')}",
            "birdeye": f"https://birdeye.so/token/{c.get('mint')}?chain=solana",
        },
    }


def fetch_trending(limit=10):
    """BirdEye 24h trending tokens for the tweet/site block."""
    payload = be_call(f"/defi/token_trending?sort_by=rank&interval=24h"
                      f"&sort_type=asc&limit={limit}&ui_amount_mode=scaled")
    data = be_data(payload)
    toks = (data or {}).get("tokens", []) if isinstance(data, dict) else []
    out = []
    for t in toks:
        if not isinstance(t, dict):
            continue
        out.append({
            "rank": int(num(t.get("rank"))),
            "name": t.get("name") or "?",
            "symbol": t.get("symbol") or "?",
            "price_usd": num(t.get("price")),
            "price_change_24h_pct": num(t.get("price24hChangePercent")),
            "volume_24h_usd": num(t.get("volume24hUSD")),
            "mcap_usd": num(t.get("marketcap")),
            "liquidity_usd": num(t.get("liquidity")),
        })
    return sorted(out, key=lambda x: x["rank"])


def run_pulse(window_min, max_enrich, top):
    fresh = discover_from_log(window_min)
    source = "launch-log+birdeye"
    if not fresh:
        fresh = discover_from_birdeye(window_min)
        source = "birdeye"
    if not fresh:
        return {"ok": False, "error": "no fresh launches found (log stale and BirdEye discovery empty)",
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    enriched = []
    for b in fresh[:max_enrich]:
        e = enrich(b["mint"])
        for k in ("name", "symbol", "created_at", "twitter", "telegram", "website"):
            if not e.get(k):
                e[k] = b.get(k)
        enriched.append(e)
    ranked = sorted((summarize(c) for c in enriched),
                    key=lambda x: x["score"], reverse=True)
    trending = fetch_trending(10)
    return {
        "ok": True,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "window_min": window_min,
        "tape_window": "30m",
        "source": source,
        "launches_seen": len(fresh),
        "enriched": len(enriched),
        "top": [{**t, "rank": i + 1} for i, t in enumerate(ranked[:top])],
        "trending": trending,
    }


def chart_sparkline(mint, minutes=60):
    """BirdEye ohlcv -> 1m close prices for the last `minutes` (sparkline)."""
    payload = be_call(f"/defi/v3/ohlcv?address={mint}&type=1m")
    data = be_data(payload)
    items = (data or {}).get("items", []) if isinstance(data, dict) else []
    closes = [num(c.get("c") if isinstance(c, dict) else None) for c in items]
    closes = [c for c in closes if c > 0]
    return closes[-minutes:]


def build_live(out_path, count=12):
    """Trending + newest memes via BirdEye, enrich, write static JSON for the site."""
    trending = fetch_trending(count)
    mints = [t.get("address") for t in
             (be_data(be_call("/defi/v3/token/meme/list?sort_by=last_trade_unix_time"
                              "&sort_type=desc&limit=50")) or {}).get("items", [])]
    seen, queue = set(), []
    for m in mints:
        if m and m not in seen:
            seen.add(m)
            queue.append(m)
    if not queue:
        # Fallback: BirdEye v3 meme endpoints are CU-heavy and may be capped
        # while cheap endpoints (token_overview, ohlcv) still work. Discover
        # fresh mints from the local launch log (real creation ts, 0 API calls)
        # and enrich via token_overview below. Keep the log's name/symbol so a
        # total enrichment failure still yields an identifiable snapshot.
        for t in discover_from_log(30) or []:
            if t["mint"] not in seen:
                seen.add(t["mint"])
                queue.append(t)
    tokens = []
    for item in queue[:count]:
        mint = item["mint"] if isinstance(item, dict) else item
        e = enrich(mint)
        if isinstance(item, dict):
            # Backfill display fields from the launch log when BirdEye
            # enrichment failed (e.g. CU cap); never clobber real data.
            if e.get("name") in (None, "?") and item.get("name") not in (None, "?"):
                e["name"] = item["name"]
            if e.get("symbol") in (None, "?") and item.get("symbol") not in (None, "?"):
                e["symbol"] = item["symbol"]
            if not e.get("created_at") and item.get("created_at"):
                e["created_at"] = item["created_at"]
            for k in ("twitter", "telegram", "website"):
                if not e.get(k) and item.get(k):
                    e[k] = item[k]
        s = summarize(e)
        s["sparkline"] = chart_sparkline(mint)
        s["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        tokens.append(s)
    if not tokens or all(t.get("symbol") in (None, "?") for t in tokens):
        # Guardrail: never clobber the last-good live file with an empty or
        # fully unidentifiable payload when the data source is down
        # (e.g. BirdEye rate limit / credits).
        print(json.dumps({"ok": False, "error": "no identifiable tokens; existing file left untouched",
                          "out": out_path}))
        return {"ok": False, "tokens": []}
    payload = {"ok": True,
               "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "source": "birdeye",
               "tokens": tokens,
               "trending": trending}
    with open(out_path, "w") as f:
        json.dump(payload, f)
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-min", type=int, default=20)
    ap.add_argument("--max-enrich", type=int, default=12)
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--build-live", metavar="OUT_JSON", default=None)
    ap.add_argument("--live-count", type=int, default=12)
    args = ap.parse_args()

    if args.build_live:
        payload = build_live(args.build_live, args.live_count)
        print(json.dumps({"ok": payload["ok"], "tokens": len(payload["tokens"]),
                          "out": args.build_live}))
        return 0 if payload["ok"] else 1

    digest = run_pulse(args.window_min, args.max_enrich, args.top)
    if args.json_only:
        print(json.dumps(digest))
        return 0
    print(json.dumps(digest, indent=2))
    print("\n--- PULSE ---")
    if not digest.get("ok") or not digest["top"]:
        print("No qualifying launches in window.")
        return 0
    for t in digest["top"]:
        why = ", ".join(t["reasons"]) or "—"
        fl = f"  [! {' '.join(t['flags'])}]" if t["flags"] else ""
        print(f"{t['rank']}. {t['name']} ({t['symbol']}) score {t['score']} — {why}{fl}")
        print(f"   mcap ${t['mcap_usd']:,.0f} | 30m vol ${t['volume_30m']:,.0f} "
              f"({t['price_change_30m_pct']:+.0f}%) | {t['holders']} holders | "
              f"{t['buys']}b/{t['sells']}s")
        print(f"   {t['links']['pumpfun']}")
    if digest.get("trending"):
        print("\n--- TRENDING 24h ---")
        for tr in digest["trending"][:5]:
            print(f"  #{tr['rank']} {tr['symbol']} {tr['price_change_24h_pct']:+.0f}% 24h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
