#!/usr/bin/env python3
"""DEX Screener REST client — free API, no auth, 60 requests/minute.

Usage:
  dex.py search <query>                          full-text token/pair search
  dex.py tokens <chain> <addr[,addr...]>         pair data for up to 30 token addresses
  dex.py pairs <chain> <pairId>                  single pair by address
  dex.py token-pairs <chain> <tokenAddress>      all pairs for one token
  dex.py boosts [latest|top]                     boosted tokens (default: latest)
  dex.py profiles [latest|updates]               token profiles (default: latest)
  dex.py takeovers                                latest community takeovers
  dex.py orders <chain> <tokenAddress>           paid orders for a token
  dex.py metas [trending|<slug>]                  trending metas or one meta's pairs

Options:
  --json        emit raw JSON instead of the human summary
  --limit N     cap rows shown (default 10 for lists)
"""
import json, os, subprocess, sys, urllib.parse

BASE = "https://api.dexscreener.com"

def get(path, params=None):
    # curl, not urllib: the egress proxy truncates large urllib responses
    # (IncompleteRead) while curl handles them fine (verified live).
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "30", "-H", "User-Agent: dexscreener-skill/1.0", url],
        capture_output=True, text=True, timeout=40)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)

def fmt_num(x):
    if x is None: return "-"
    try: x = float(x)
    except: return str(x)
    if abs(x) >= 1e9: return f"${x/1e9:.2f}B"
    if abs(x) >= 1e6: return f"${x/1e6:.2f}M"
    if abs(x) >= 1e3: return f"${x/1e3:.1f}K"
    return f"${x:.2f}"

def pair_row(p):
    base = p.get("baseToken", {}) or {}
    tx = p.get("txns", {}).get("h24", {}) or {}
    vol = p.get("volume", {}) or {}
    pc = p.get("priceChange", {}) or {}
    liq = (p.get("liquidity") or {}).get("usd")
    return (f"{base.get('symbol','?'):12} {p.get('chainId','?'):10} {p.get('dexId','?'):10} "
            f"px {p.get('priceUsd') or '?':>12} mcap {fmt_num(p.get('marketCap')):>10} "
            f"liq {fmt_num(liq):>10} vol24 {fmt_num(vol.get('h24')):>10} "
            f"ch24 {pc.get('h24','?')}% buys {tx.get('buys','?')}/{tx.get('sells','?')} "
            f"{base.get('address','')}")

def show_pairs(pairs, limit, raw):
    pairs = pairs or []
    if raw:
        print(json.dumps(pairs[:limit], indent=2)); return
    print(f"{len(pairs)} pairs")
    for p in pairs[:limit]:
        print(" ", pair_row(p))
        print("    ", p.get("url"))

def cmd_search(q, limit, raw):
    d = get("/latest/dex/search", {"q": q})
    show_pairs(d.get("pairs"), limit, raw)

def cmd_tokens(chain, addrs, limit, raw):
    d = get(f"/tokens/v1/{chain}/{addrs}")
    show_pairs(d, limit, raw)

def cmd_pairs(chain, pair_id, limit, raw):
    d = get(f"/latest/dex/pairs/{chain}/{pair_id}")
    show_pairs(d.get("pairs"), limit, raw)

def cmd_token_pairs(chain, token, limit, raw):
    d = get(f"/token-pairs/v1/{chain}/{token}")
    show_pairs(d, limit, raw)

def cmd_boosts(which, limit, raw):
    d = get(f"/token-boosts/{which}/v1")
    if raw:
        print(json.dumps(d[:limit], indent=2)); return
    print(f"{len(d)} boosted tokens ({which})")
    for b in d[:limit]:
        amt = f"{b.get('amount')}/{b.get('totalAmount')}" if b.get("amount") else "?"
        print(f"  {b.get('chainId'):10} {b.get('tokenAddress')} boost {amt}")
        print(f"    {(b.get('description') or '')[:80]} {b.get('url')}")

def cmd_profiles(which, limit, raw):
    path = "/token-profiles/latest/v1" if which == "latest" else "/token-profiles/recent-updates/v1"
    d = get(path)
    if raw:
        print(json.dumps(d[:limit], indent=2)); return
    print(f"{len(d)} token profiles ({which})")
    for t in d[:limit]:
        links = ",".join(l.get("type") or "?" for l in (t.get("links") or [])[:4])
        print(f"  {t.get('chainId'):10} {t.get('tokenAddress')}")
        print(f"    {(t.get('description') or '')[:80]} [{links}] {t.get('url')}")

def cmd_takeovers(limit, raw):
    d = get("/community-takeovers/latest/v1")
    if raw:
        print(json.dumps(d[:limit], indent=2)); return
    print(f"{len(d)} community takeovers")
    for t in d[:limit]:
        print(f"  {t.get('chainId'):10} {t.get('tokenAddress')} claimed {t.get('claimDate')}")
        print(f"    {(t.get('description') or '')[:80]} {t.get('url')}")

def cmd_orders(chain, token, raw):
    d = get(f"/orders/v1/{chain}/{token}")
    print(json.dumps(d, indent=2))

def cmd_metas(slug, limit, raw):
    if slug == "trending":
        d = get("/metas/trending/v1")
        if raw:
            print(json.dumps(d[:limit], indent=2)); return
        for m in d[:limit]:
            chg = (m.get("marketCapChange") or {}).get("h24", "?")
            print(f"  {m.get('slug'):24} tokens {m.get('tokenCount'):>4} mcap {fmt_num(m.get('marketCap')):>10} "
                  f"vol {fmt_num(m.get('volume')):>10} ch24 {chg}%")
            print(f"    {(m.get('description') or '')[:100]}")
    else:
        d = get(f"/metas/meta/v1/{slug}")
        if raw:
            print(json.dumps(d, indent=2)); return
        print(f"meta: {d.get('name')} ({d.get('slug')}) mcap {fmt_num(d.get('marketCap'))}")
        show_pairs(d.get("pairs"), limit, raw)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raw = "--json" in sys.argv
    lim = 10
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    if not args:
        print(__doc__); sys.exit(1)
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "search" and rest: cmd_search(" ".join(rest), lim, raw)
        elif cmd == "tokens" and len(rest) >= 2: cmd_tokens(rest[0], rest[1], lim, raw)
        elif cmd == "pairs" and len(rest) >= 2: cmd_pairs(rest[0], rest[1], lim, raw)
        elif cmd == "token-pairs" and len(rest) >= 2: cmd_token_pairs(rest[0], rest[1], lim, raw)
        elif cmd == "boosts": cmd_boosts(rest[0] if rest and rest[0] in ("latest", "top") else "latest", lim, raw)
        elif cmd == "profiles": cmd_profiles(rest[0] if rest and rest[0] in ("latest", "updates") else "latest", lim, raw)
        elif cmd == "takeovers": cmd_takeovers(lim, raw)
        elif cmd == "orders" and len(rest) >= 2: cmd_orders(rest[0], rest[1], raw)
        elif cmd == "metas": cmd_metas(rest[0] if rest else "trending", lim, raw)
        else: print(__doc__); sys.exit(1)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr); sys.exit(2)

if __name__ == "__main__":
    main()
