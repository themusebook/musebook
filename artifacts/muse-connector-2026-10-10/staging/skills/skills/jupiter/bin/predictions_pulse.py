#!/usr/bin/env python3
"""Hourly prediction-markets pulse: fetch latest markets, build Clawd's
watchlist ("picks"), publish as a static JSON the site polls.

Reads:  Jupiter Prediction API via jup_predict.py (read-only).
        Polymarket trending via the Jupiter proxy, with a direct
        gamma-api.polymarket.com fallback (curl) when the proxy times out.
Writes: ~/workspace/musebook/web/live/predictions.json + copies where the
        React build serves it (dist/live) and where rebuilds pick it up
        (public/live). Publishing to the live site is handled by the separate
        musebook-live-data-deploy job (every 30m) — this script only writes
        the JSON files, it never deploys. (The worker /api/predictions/ingest
        KV path is retired: the account's free-tier KV write quota is
        exhausted by the launch-tank box's 10s pushes, so KV writes 500.)

Picks are market-implied probabilities from live order data — data, not
advice. No order is built, no trade is placed, nothing is signed.
"""
import sys
import os
import json
import time
import subprocess

JUP = "/home/hatch/workspace/skills/jupiter/bin/jup_predict.py"
OUT = "/home/hatch/workspace/musebook/web/live/predictions.json"
# React production is the live site now: write the JSON where the deployed
# React build serves it (dist/live) and where rebuilds pick it up (public/live).
OUT_DIST = "/home/hatch/workspace/musebook/web-react/dist/live/predictions.json"
OUT_PUBLIC = "/home/hatch/workspace/musebook/web-react/public/live/predictions.json"


def jup(*args):
    r = subprocess.run(["python3", JUP] + list(args),
                       capture_output=True, text=True, timeout=60)
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"jup_predict returned non-JSON (rc={r.returncode}): "
            f"{r.stdout[:120]!r}") from e
    if isinstance(payload, dict) and not payload.get("ok", True):
        raise RuntimeError(f"jup_predict error: {payload.get('error', 'unknown')}")
    return payload


GAMMA_URL = ("https://gamma-api.polymarket.com/events"
             "?active=true&closed=false&archived=false"
             "&order=volume24hr&ascending=false&limit=12")

def gamma_trending(limit_events=8):
    """Direct Polymarket Gamma API fallback when Jupiter's prediction proxy
    times out. Returns event dicts shaped like jup_predict's output:
    {title, volumeUsd, markets:[{marketId, status, buyYesUsd, buyNoUsd}]}.
    Uses curl, not urllib: the egress proxy truncates large urllib responses."""
    r = subprocess.run(["curl", "-sS", "-m", "25", GAMMA_URL],
                       capture_output=True, text=True, timeout=40)
    if r.returncode != 0:
        raise RuntimeError(f"gamma curl failed: {r.stderr[-120:]}")
    try:
        events = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"gamma returned non-JSON: {e}") from e
    out = []
    for e in events[:limit_events]:
        markets = []
        for m in (e.get("markets") or [])[:4]:
            prices = m.get("outcomePrices")
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except Exception:
                    prices = None
            if not prices or len(prices) < 2:
                continue
            try:
                yes, no = float(prices[0]), float(prices[1])
            except (ValueError, TypeError):
                continue
            is_open = bool(m.get("active")) and not m.get("closed")
            markets.append({
                "marketId": str(m.get("id") or m.get("conditionId") or ""),
                "status": "open" if is_open else "closed",
                # price strings: parse_price_usd treats floats as micros
                "buyYesUsd": f"{yes:.4f}",
                "buyNoUsd": f"{no:.4f}",
            })
        out.append({
            "title": e.get("title"),
            "volumeUsd": e.get("volume24hr") or e.get("volume"),
            "markets": markets,
        })
    if not out:
        raise RuntimeError("gamma returned no events")
    return out


def parse_price_usd(v):
    """jup_predict.py formats prices as '$0.084' strings; accept those or raw micros."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v / 1_000_000
    s = str(v).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def main():
    degraded = []  # upstream feeds that failed this run

    # ---- Forecast: live bisonfi rounds ----
    forecast = []
    try:
        d = jup("events", "--provider", "bisonfi", "--filter", "live",
                "--include-markets", "--end", "6")
        now = int(time.time())
        for e in d.get("events", [])[:6]:
            mkts = {m.get("outcomeSide"): m for m in e.get("markets", [])}
            up, down = mkts.get("up"), mkts.get("down")
            close = (up or down or {}).get("closeTime")
            forecast.append({
                "title": e.get("title"),
                "eventId": e.get("eventId"),
                "upMarketId": up.get("marketId") if up else None,
                "downMarketId": down.get("marketId") if down else None,
                "tradable": bool((up or {}).get("tradable")),
                "closesInMin": round((close - now) / 60, 1) if close else None,
                "upcomeFirst": None,
            })
    except Exception as ex:
        print(f"forecast fetch failed: {ex}", file=sys.stderr)
        degraded.append("forecast")

    # ---- Polymarket trending (Jupiter proxy, Gamma direct fallback) ----
    trending = []
    cands = []
    try:
        d = jup("events", "--provider", "polymarket", "--filter", "trending",
                "--include-markets", "--end", "8")
        events = d.get("events", [])
        if not events:
            raise RuntimeError("jup_predict returned ok but zero events")
    except Exception as ex:
        print(f"jup polymarket proxy failed ({ex}); "
              "falling back to direct Gamma API", file=sys.stderr)
        try:
            events = gamma_trending()
            print("gamma fallback: got %d events" % len(events), file=sys.stderr)
        except Exception as ex2:
            print(f"gamma fallback failed: {ex2}", file=sys.stderr)
            degraded.append("trending")
            events = []
    try:
        for e in events:
            vol = e.get("volumeUsd")
            for m in (e.get("markets", []) or [])[:4]:
                if m.get("status") != "open":
                    continue
                yes = parse_price_usd(m.get("buyYesUsd"))
                no = parse_price_usd(m.get("buyNoUsd"))
                if yes is None or no is None or (yes + no) <= 0:
                    continue
                implied = yes / (yes + no)
                item = {
                    "eventTitle": e.get("title"),
                    "marketId": m.get("marketId"),
                    "yesPrice": round(yes, 4),
                    "noPrice": round(no, 4),
                    "impliedYesPct": round(implied * 100, 1),
                    "volumeUsd": vol,
                }
                trending.append(item)
                cands.append((abs(implied - 0.5), item))
    except Exception as ex:
        print(f"trending fetch failed: {ex}", file=sys.stderr)
        degraded.append("trending")

    # Any upstream failure = degraded run: do NOT clobber the last good
    # snapshot with empty feeds. Keep the site on the previous data and
    # exit non-zero so the cron flags the run for repair.
    if degraded:
        print(json.dumps({"ok": False, "degraded": degraded,
                          "error": "upstream fetch failed; kept last good snapshot"}))
        return 1

    # ---- Clawd's watchlist: most lopsided high-signal markets (one per event) ----
    best = {}
    for conv, item in cands:
        t = item["eventTitle"]
        if t not in best or conv > best[t][0]:
            best[t] = (conv, item)
    ranked = sorted(best.values(), key=lambda x: x[0], reverse=True)
    picks = []
    for conv, item in ranked[:6]:
        side = "YES" if item["impliedYesPct"] >= 50 else "NO"
        pct = item["impliedYesPct"] if side == "YES" else round(100 - item["impliedYesPct"], 1)
        picks.append({
            **item,
            "lean": side,
            "leanPct": pct,
            "why": (f"Market prices {side} at {pct}% "
                    f"({item['volumeUsd']} vol) — market-implied odds, data not advice."),
        })

    payload = {
        "forecast": forecast,
        "trending": trending[:12],
        "picks": picks,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # ---- publish as static JSON (deploy is a separate job's concern) ----
    payload_str = json.dumps(payload)
    for path in (OUT, OUT_DIST, OUT_PUBLIC):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(payload_str)
    print(json.dumps({
        "ok": True,
        "forecast_rounds": len(forecast),
        "trending": len(trending),
        "picks": len(picks),
        "pick_titles": [p["eventTitle"] for p in picks],
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
