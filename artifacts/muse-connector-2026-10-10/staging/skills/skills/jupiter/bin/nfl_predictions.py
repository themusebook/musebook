#!/usr/bin/env python3
"""Sunday NFL predictions: every game on today's slate, market-implied win
probabilities from Polymarket via the Jupiter Prediction API (read-only).

For each NFL team, discover game events closing on the target Sunday,
pull the two moneyline markets per game, normalize buyYes micros into
implied win %.

Writes: ~/workspace/musebook/web/live/nfl-predictions.json
        + web-react/dist/live + web-react/public/live mirrors.
Then composes one slate-summary tweet (data-only, market-implied, no
advice language) and posts it from @clawddevs.

Read-only market data. No trades, no orders, nothing signed.
"""
import sys
import os
import re
import json
import time
import subprocess
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

JUP = "/home/hatch/workspace/skills/jupiter/bin/jup_predict.py"
POST = "/home/hatch/workspace/skills/x-connect/bin/post.py"
OUT = "/home/hatch/workspace/musebook/web/live/nfl-predictions.json"
OUT_DIST = "/home/hatch/workspace/musebook/web-react/dist/live/nfl-predictions.json"
OUT_PUBLIC = "/home/hatch/workspace/musebook/web-react/public/live/nfl-predictions.json"
DEPLOY = "/home/hatch/workspace/musebook/deploy_react_production.py"
# Live traffic is Vercel (GitHub -> Vercel), not Cloudflare Pages:
# deploy_react_production.py is a no-op for users. Publish the snapshot
# through the GitHub/Vercel live-data publisher instead.
PUBLISH = "/home/hatch/workspace/musebook/push_live_data_github.py"
ET = ZoneInfo("America/New_York")

TEAMS = ["Vikings", "Bears", "Eagles", "Titans", "Steelers", "Patriots",
         "Saints", "Ravens", "Bengals", "Texans", "Panthers", "Falcons",
         "Browns", "Buccaneers", "Packers", "Jets", "Raiders", "Chargers",
         "Jaguars", "Broncos", "Dolphins", "49ers", "Seahawks", "Cardinals",
         "Commanders", "Cowboys", "Colts", "Chiefs", "Rams", "Lions",
         "Bills", "Giants"]
TEAM_SET = set(TEAMS)
# Sanity floor: a real Sunday slate is 12-16 games. Anything far below this
# means discovery broke — refuse to publish rather than tweet garbage.
MIN_GAMES = 10

# Aliases: market titles occasionally use a fuller/abbreviated team name.
TEAM_ALIASES = {
    "New York Jets": "Jets", "NY Jets": "Jets",
    "New York Giants": "Giants", "NY Giants": "Giants",
    "New England Patriots": "Patriots",
    "Tampa Bay Buccaneers": "Buccaneers",
    "Las Vegas Raiders": "Raiders",
    "Los Angeles Chargers": "Chargers", "LA Chargers": "Chargers",
    "Los Angeles Rams": "Rams", "LA Rams": "Rams",
    "Kansas City Chiefs": "Chiefs",
    "San Francisco 49ers": "49ers",
    "Green Bay Packers": "Packers",
    "New Orleans Saints": "Saints",
    "Arizona Cardinals": "Cardinals",
    "Washington Commanders": "Commanders",
    "Jacksonville Jaguars": "Jaguars",
}


def canon_team(name):
    name = (name or "").strip()
    if name in TEAM_SET:
        return name
    return TEAM_ALIASES.get(name)

SEASON_WEEK1_MON = date(2026, 9, 7)


# ---- Book lines + Clawd's final-score engine -------------------------------
# Curated consensus spreads/totals per week (keyed by eventId, with a
# (away, home) fallback since eventIds rotate weekly). Spread is the
# favorite's margin (positive number); total is the game O/U.
# Lines verified from book consensus; Polymarket moneyline prices come
# live from the Jupiter Prediction API per run.
BOOK_LINES = {
    # 2026 Week 3 (Sun Sep 27 + Mon Sep 28)
    "POLY-864726": {"spread": 7.0, "total": 50.5},    # Chargers @ Bills
    "POLY-864730": {"spread": 2.5, "total": 42.5},    # Panthers @ Browns
    "POLY-864734": {"spread": 6.5, "total": 47.5},    # Jets @ Lions
    "POLY-864736": {"spread": 2.0, "total": 42.5},    # Texans @ Colts
    "POLY-864741": {"spread": 3.0, "total": 45.5},    # Patriots @ Jaguars
    "POLY-864744": {"spread": 10.5, "total": 46.5},   # Chiefs @ Dolphins
    "POLY-864747": {"spread": 2.5, "total": 38.5},    # Titans @ Giants
    "POLY-864751": {"spread": 3.5, "total": 42.5},    # Bengals @ Steelers
    "POLY-864754": {"spread": 8.0, "total": 40.5},    # Seahawks @ Commanders
    "POLY-864757": {"spread": 9.0, "total": 48.0},    # Cardinals @ 49ers
    "POLY-864759": {"spread": 1.5, "total": 42.0},    # Vikings @ Buccaneers
    "POLY-864723": {"spread": 2.5, "total": 51.5},    # Ravens @ Cowboys
    "POLY-864761": {"spread": 3.0, "total": 43.5},    # Raiders @ Saints
    "POLY-864764": {"spread": 2.5, "total": 44.5},    # Rams @ Broncos
    "POLY-870381": {"spread": 1.5, "total": 46.5},    # Eagles @ Bears (Mon)
}
BOOK_LINES_MATCHUP = {
    # (away, home) fallbacks
    ("Chargers", "Bills"): (7.0, 50.5),
    ("Panthers", "Browns"): (2.5, 42.5),
    ("Jets", "Lions"): (6.5, 47.5),
    ("Texans", "Colts"): (2.0, 42.5),
    ("Patriots", "Jaguars"): (3.0, 45.5),
    ("Chiefs", "Dolphins"): (10.5, 46.5),
    ("Titans", "Giants"): (2.5, 38.5),
    ("Bengals", "Steelers"): (3.5, 42.5),
    ("Seahawks", "Commanders"): (8.0, 40.5),
    ("Cardinals", "49ers"): (9.0, 48.0),
    ("Vikings", "Buccaneers"): (1.5, 42.0),
    ("Ravens", "Cowboys"): (2.5, 51.5),
    ("Raiders", "Saints"): (3.0, 43.5),
    ("Rams", "Broncos"): (2.5, 44.5),
    ("Eagles", "Bears"): (1.5, 46.5),
}

COMMON_SCORES = [3, 6, 7, 9, 10, 13, 14, 16, 17, 20, 21, 23, 24, 27, 28,
                 30, 31, 34, 35, 37, 38, 41, 42, 44, 45]


def footballify(raw):
    """Snap a raw point value to the nearest realistic football score."""
    return min(COMMON_SCORES, key=lambda s: (abs(s - raw), s))


def predicted_final_score(spread, total):
    """Blend book spread/total into a realistic final score.
    Returns (fav_points, dog_points)."""
    fav_raw = (total + spread) / 2.0
    dog_raw = (total - spread) / 2.0
    fav, dog = footballify(fav_raw), footballify(dog_raw)
    if fav <= dog:
        # keep the favorite on top with at least a field goal of daylight
        fav = footballify(dog_raw + spread + 1.5)
        if fav <= dog:
            fav = dog + 3
    return fav, dog


def enrich_game(game):
    """Attach book spread/total + Clawd's predicted final score. The winner
    is always the Polymarket moneyline favorite; the score is blended from
    the book line so the margin and total stay honest."""
    line = BOOK_LINES.get(game.get("eventId") or "")
    if not line:
        fb = BOOK_LINES_MATCHUP.get((game.get("away"), game.get("home")))
        if fb:
            line = {"spread": fb[0], "total": fb[1]}
    if not line:
        return game
    spread, total = line["spread"], line["total"]
    fav_pts, dog_pts = predicted_final_score(spread, total)
    fav, dog = game["favorite"], game["underdog"]
    fav_is_home = (fav == game.get("home"))
    game["spread"] = spread
    game["spreadLine"] = f"{fav} -{spread:g}"
    game["total"] = total
    game["predictedScore"] = {
        "favorite": fav_pts,
        "underdog": dog_pts,
        "favoriteTeam": fav,
        "underdogTeam": dog,
    }
    game["predictedFinal"] = f"{fav} {fav_pts}, {dog} {dog_pts}"
    game["scoreAway"], game["scoreHome"] = (
        (dog_pts, fav_pts) if fav_is_home else (fav_pts, dog_pts)
    )
    game["oddsSource"] = ("Polymarket moneyline via Jupiter Prediction API "
                          "+ book spread/total consensus")
    return game


def jup(*args, retries=5):
    """Call jup_predict.py with retries — the prediction API drops requests
    transiently (timeouts, 5xx). A dropped search must not silently drop a
    whole game from the slate."""
    last = None
    for attempt in range(retries):
        try:
            r = subprocess.run(["python3", JUP] + list(args),
                               capture_output=True, text=True, timeout=90)
            return json.loads(r.stdout)
        except Exception as ex:
            last = ex
            wait = min(2 ** attempt, 15)
            print(f"jup {' '.join(args[:3])} attempt {attempt + 1} failed: "
                  f"{ex}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"jup {' '.join(args[:3])} failed after {retries}: {last}")


def micros_to_usd(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v / 1_000_000
    s = str(v).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def week_of(d):
    return ((d - SEASON_WEEK1_MON).days // 7) + 1


def discover_games(target):
    """Return {eventId: event} for NFL games closing on target Sunday (ET).

    Each candidate must be a real NFL matchup: BOTH sides of the title must
    resolve to one of the 32 NFL teams (kills NHL/soccer lookalikes like the
    Florida Panthers or Belgian soccer clubs that share a name search hit).

    Serial on purpose: the prediction API throttles concurrent searches and
    parallel runs silently dropped whole games from the slate.
    """
    games = {}
    for team in TEAMS:
        try:
            d = jup("events-search", "--provider", "polymarket",
                    "--query", team, "--limit", "10")
        except Exception as ex:
            print(f"search {team} failed after retries: {ex}", file=sys.stderr)
            continue
        for e in d.get("events", []):
            title = e.get("title") or ""
            if " vs. " not in title:
                continue
            parts = title.split(" vs. ")
            if len(parts) != 2:
                continue
            away = canon_team(parts[0])
            home = canon_team(parts[1])
            if not away or not home:
                # not a valid NFL matchup (NHL, soccer, futures, etc.)
                continue
            eid = e.get("eventId")
            if eid in games:
                continue
            games[eid] = e
    return games


def game_date_et(m):
    ct = m.get("closeTime")
    if not ct:
        return None
    return datetime.fromtimestamp(ct, tz=ET).date()


def kickoff_from_rules(rules):
    if not rules:
        return None
    m = re.search(r"scheduled for (\w+ \d+) at ([\d:]+\s*[AP]M) ET", rules)
    return f"{m.group(1)} {m.group(2)} ET" if m else None


def markets_for(eid):
    try:
        d = jup("event-markets", eid)
    except Exception as ex:
        print(f"event-markets {eid} failed: {ex}", file=sys.stderr)
        return []
    mkts = d.get("data", d.get("markets", []))
    team_mkts = [m for m in mkts
                 if m.get("status") == "open"
                 and m.get("sportsMarketType") == "moneyline"]
    return team_mkts


def price_event(eid, e, target):
    """Price one discovered event. Returns (game_dict, None) or (None, reason).
    Reasons: 'transient' (fetch/pricing failure — worth one more attempt),
    'wrong-date' (event isn't on the target Sunday), 'non-nfl'."""
    title = e.get("title", "")
    parts = title.split(" vs. ")
    if len(parts) != 2:
        return None, "non-nfl"
    away, home = canon_team(parts[0].strip()), canon_team(parts[1].strip())
    if not away or not home:
        print(f"skip {title}: non-NFL matchup", file=sys.stderr)
        return None, "non-nfl"
    mkts = markets_for(eid)
    if len(mkts) < 2:
        # match by title to be safe; take first two distinct team markets
        seen, clean = set(), []
        for m in mkts:
            t = (m.get("title") or "").strip()
            if t and t not in seen:
                seen.add(t)
                clean.append(m)
        mkts = clean
    if len(mkts) < 2:
        print(f"skip {title}: only {len(mkts)} team markets", file=sys.stderr)
        return None, "transient"
    rows = []
    for m in mkts[:2]:
        t = canon_team((m.get("title") or "").strip())
        yes = micros_to_usd((m.get("pricing") or {}).get("buyYesPriceUsd"))
        vol = (m.get("pricing") or {}).get("volume")
        if t and yes is not None and yes > 0:
            rows.append((t, yes, m.get("marketId"), vol))
    if len(rows) < 2:
        print(f"skip {title}: unusable pricing", file=sys.stderr)
        return None, "transient"
    tot = rows[0][1] + rows[1][1]
    rows = sorted([(t, round(yes / tot * 100, 1), mid, vol)
                   for t, yes, mid, vol in rows],
                  key=lambda r: -r[1])
    # verify this event actually closes on the target Sunday (ET)
    gd = game_date_et(mkts[0])
    if gd and gd != target:
        print(f"skip {title}: closes {gd} not {target}", file=sys.stderr)
        return None, "wrong-date"
    kickoff = kickoff_from_rules(mkts[0].get("rulesPrimary"))
    return ({
        "eventId": eid,
        "title": title,
        "away": away,
        "home": home,
        "kickoffEt": kickoff,
        "favorite": rows[0][0],
        "favoritePct": rows[0][1],
        "underdog": rows[1][0],
        "underdogPct": rows[1][1],
        "marketIds": [rows[0][2], rows[1][2]],
    }, None)


def build(target, deploy=True, tweet=True):
    raw = discover_games(target)
    games = []
    mop_up = []  # (eid, e) candidates that failed transiently — retry once
    for eid, e in sorted(raw.items()):
        game, reason = price_event(eid, e, target)
        if game:
            games.append(game)
        elif reason == "transient":
            mop_up.append((eid, e))
    if mop_up:
        print(f"mop-up pass: retrying {len(mop_up)} transient failures",
              file=sys.stderr)
        time.sleep(5)
        for eid, e in mop_up:
            game, reason = price_event(eid, e, target)
            if game:
                games.append(game)
            else:
                print(f"mop-up failed {e.get('title')}: {reason}",
                      file=sys.stderr)
    # sort by kickoff, then favorite pct desc
    games.sort(key=lambda g: (g["kickoffEt"] or "zzz", -g["favoritePct"]))
    # Clawd's final-score call on every game with a book line
    games = [enrich_game(g) for g in games]

    if len(games) < MIN_GAMES:
        # Refuse to publish a partial/garbage board. Never replace a good
        # snapshot with a thin one, and never tweet a broken slate.
        print(json.dumps({"ok": False, "games": len(games),
                          "error": f"only {len(games)} games found, "
                                   f"below floor of {MIN_GAMES}; refusing to "
                                   f"publish/tweet"}),
              file=sys.stderr)
        return 1

    payload = {
        "date": target.isoformat(),
        "week": week_of(target),
        "games": games,
        "gameCount": len(games),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Market-implied win probabilities from Polymarket order "
                "books via Jupiter Prediction API; final scores blended from "
                "book spread/total consensus. Data, not betting advice.",
    }
    blob = json.dumps(payload)
    # Atomic replacement: never leave a half-written snapshot on disk.
    for path in (OUT, OUT_DIST, OUT_PUBLIC):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(blob)
        os.replace(tmp, path)

    result = {"ok": True, "games": len(games)}
    if tweet and games:
        text = compose_tweet(payload)
        r = subprocess.run(["python3", POST, "--text", text],
                           capture_output=True, text=True, timeout=120)
        result["tweet_stdout"] = r.stdout[-400:]
        result["tweet_stderr"] = r.stderr[-400:] if r.stderr else None
        result["tweet_ok"] = r.returncode == 0
    if deploy:
        # Publish the enriched snapshot to production via the GitHub/Vercel
        # live-data path (push_live_data_github.py handles byte-compare and
        # only commits on real changes).
        dep = subprocess.run(["python3", PUBLISH],
                             capture_output=True, text=True, timeout=300)
        result["deploy_ok"] = dep.returncode == 0
        result["deploy_stdout"] = dep.stdout[-300:] if dep.stdout else None
        if dep.returncode != 0:
            result["deploy_error"] = dep.stderr[-300:]
    print(json.dumps(result, indent=1))
    return 0


def compose_tweet(payload):
    week = payload["week"]
    games = payload["games"]
    top = sorted(games, key=lambda g: -g["favoritePct"])[:3]
    lines = [f"\U0001F995 NFL Sunday — Week {week} market board \U0001F3C8",
             f"{len(games)} games, all market-implied odds:"]
    for g in top:
        lines.append(f"\u2022 {g['favorite']} {g['favoritePct']:.0f}% over {g['underdog']}")
    lines += ["full slate \U0001F447",
              "musebook.trade",
              "",
              "powered by $CLAWD on pump.fun",
              "sent from my @muse app"]
    text = "\n".join(lines)
    if len(text) > 280:  # hard guard: drop the third lean line
        lines = [l for i, l in enumerate(lines) if i != 4]
        text = "\n".join(lines)
    return text


def main():
    argv = sys.argv[1:]
    target = None
    deploy = "--no-deploy" not in argv
    tweet = "--no-tweet" not in argv
    for i, a in enumerate(argv):
        if a == "--date" and i + 1 < len(argv):
            target = date.fromisoformat(argv[i + 1])
    if target is None:
        today = datetime.now(ET).date()
        # run lands on Sunday; if not Sunday, roll back to the most recent one
        delta = (today.weekday() + 1) % 7
        target = today - timedelta(days=delta)
    return build(target, deploy=deploy, tweet=tweet)


if __name__ == "__main__":
    sys.exit(main())
