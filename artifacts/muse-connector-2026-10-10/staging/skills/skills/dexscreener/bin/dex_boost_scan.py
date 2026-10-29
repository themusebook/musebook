#!/usr/bin/env python3
"""DEX Screener boost scan — flags NEW Solana boosted tokens with real liquidity.

Streams the boosts-latest WebSocket for a window, dedupes against a seen-state
file, enriches each new Solana boost with pair data (price, mcap, liquidity,
volume, buys/sells), and reports only those passing the liquidity filters.

Usage:
  dex_boost_scan.py [--seconds N] [--min-liq USD] [--min-mcap USD]
                    [--min-buys N] [--state PATH] [--json]

Output: human-readable report (default) or JSON (--json). Exit 0 always;
prints "NO_NEW_QUALIFYING_BOOSTS" when nothing passes (cron-friendly).
"""
import json, os, subprocess, sys, time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(SKILL_DIR, "bin")
DEFAULT_STATE = os.path.expanduser("~/.config/dexscreener/seen_boosts.json")

def arg(name, default):
    i = sys.argv.index(name) + 1 if name in sys.argv else None
    return sys.argv[i] if i and i < len(sys.argv) else default

def fmt_num(x):
    if x is None: return "-"
    try: x = float(x)
    except: return str(x)
    if abs(x) >= 1e9: return f"${x/1e9:.2f}B"
    if abs(x) >= 1e6: return f"${x/1e6:.2f}M"
    if abs(x) >= 1e3: return f"${x/1e3:.1f}K"
    return f"${x:.2f}"

def load_state(path):
    try:
        with open(path) as f: return json.load(f)
    except: return {}

def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # prune entries older than 7 days
    cutoff = time.time() - 7 * 86400
    state = {k: v for k, v in state.items() if v > cutoff}
    with open(path, "w") as f: json.dump(state, f)

def stream_boosts(seconds):
    """Run dex_stream.mjs, return list of boost item dicts (solana only)."""
    r = subprocess.run(
        ["node", os.path.join(BIN, "dex_stream.mjs"),
         "--channel", "boosts-latest", "--seconds", str(seconds),
         "--chain", "solana"],
        capture_output=True, text=True, timeout=int(seconds) + 60)
    items = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"): continue
        try: items.append(json.loads(line))
        except: pass
    return items

def enrich(addr):
    """Pair data for a token; returns best-liquidity pair dict or None."""
    r = subprocess.run(
        [os.path.join(BIN, "dex.py"), "tokens", "solana", addr, "--json"],
        capture_output=True, text=True, timeout=60)
    try: pairs = json.loads(r.stdout)
    except: return None
    if not pairs: return None
    pairs.sort(key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
    return pairs[0]

def main():
    seconds = int(arg("--seconds", "60"))
    min_liq = float(arg("--min-liq", "10000"))
    min_mcap = float(arg("--min-mcap", "25000"))
    min_buys = int(arg("--min-buys", "10"))
    state_path = arg("--state", DEFAULT_STATE)
    as_json = "--json" in sys.argv

    seen = load_state(state_path)
    now = time.time()
    fresh = []
    for item in stream_boosts(seconds):
        addr = item.get("tokenAddress")
        if not addr or addr in seen: continue
        seen[addr] = now
        fresh.append(item)
    save_state(state_path, seen)

    qualifying = []
    for item in fresh:
        addr = item["tokenAddress"]
        p = enrich(addr)
        if not p: continue
        liq = ((p.get("liquidity") or {}).get("usd")) or 0
        mcap = p.get("marketCap") or 0
        tx = ((p.get("txns") or {}).get("h24")) or {}
        buys = tx.get("buys") or 0
        if liq >= min_liq and mcap >= min_mcap and buys >= min_buys:
            base = p.get("baseToken") or {}
            vol = p.get("volume") or {}
            pc = p.get("priceChange") or {}
            qualifying.append({
                "symbol": base.get("symbol"), "name": base.get("name"),
                "address": addr, "dex": p.get("dexId"),
                "priceUsd": p.get("priceUsd"), "mcap": mcap, "liquidity": liq,
                "vol24": vol.get("h24"), "priceChange24": pc.get("h24"),
                "buys24": buys, "sells24": tx.get("sells"),
                "boost": item.get("boost"),
                "description": (item.get("description") or "")[:160] or None,
                "links": item.get("links"),
                "url": p.get("url"),
            })
    qualifying.sort(key=lambda q: q["liquidity"], reverse=True)

    if as_json:
        print(json.dumps({"new_boosts_seen": len(fresh),
                          "qualifying": qualifying}, indent=2))
        return
    print(f"new Solana boosts seen: {len(fresh)} | qualifying: {len(qualifying)} "
          f"(liq>={fmt_num(min_liq)} mcap>={fmt_num(min_mcap)} buys24>={min_buys})")
    if not qualifying:
        print("NO_NEW_QUALIFYING_BOOSTS")
        return
    for q in qualifying:
        print(f"\n  {q['symbol']} ({q['name']}) on {q['dex']}  boost {q['boost']}")
        print(f"    mcap {fmt_num(q['mcap'])}  liq {fmt_num(q['liquidity'])}  "
              f"vol24 {fmt_num(q['vol24'])}  ch24 {q['priceChange24']}%  "
              f"buys/sells {q['buys24']}/{q['sells24']}")
        if q["description"]: print(f"    {q['description']}")
        print(f"    {q['url']}")
        print(f"    {q['address']}")

if __name__ == "__main__":
    main()
