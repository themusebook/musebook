#!/usr/bin/env python3
"""Push the Sunday NFL slate from nfl-predictions.json into Convex
(nfl_picks table) via the worker-proxied upsert endpoint.

Best-effort: on any failure it logs to stderr and exits 0 (the JSON file
and the tweet are the primary deliverables of the Sunday run).

Called by the Sunday cron AFTER nfl_predictions.py writes the JSON.

Filters to NFL-vs-NFL matchups only — the Jupiter events-search discovery
sometimes matches same-named teams in other leagues (e.g. NHL Hurricanes,
KBO Lions), and those must never pollute the pick-tracking tables.
"""
import sys
import json
import subprocess
import tempfile
import os

JSON_PATH = "/home/hatch/workspace/musebook/web/live/nfl-predictions.json"
UPSERT_URL = "https://musebook.trade/api/v1/nfl/picks/upsert"

# Must stay in sync with TEAMS in nfl_predictions.py
TEAMS = {"Vikings", "Bears", "Eagles", "Titans", "Steelers", "Patriots",
         "Saints", "Ravens", "Bengals", "Texans", "Panthers", "Falcons",
         "Browns", "Buccaneers", "Packers", "Jets", "Raiders", "Chargers",
         "Jaguars", "Broncos", "Dolphins", "49ers", "Seahawks", "Cardinals",
         "Commanders", "Cowboys", "Colts", "Chiefs", "Rams", "Lions",
         "Bills", "Giants"}


def main():
    try:
        with open(JSON_PATH) as f:
            payload = json.load(f)
    except Exception as ex:
        print(f"CONVEX_SYNC=failed: cannot read {JSON_PATH}: {ex}",
              file=sys.stderr)
        return 0

    week = payload.get("week")
    season_date = payload.get("date")
    games = payload.get("games", [])
    if not isinstance(week, int) or not season_date:
        print("CONVEX_SYNC=failed: JSON missing week/date", file=sys.stderr)
        return 0

    picks = []
    skipped = 0
    for g in games:
        away = g.get("away", "")
        home = g.get("home", "")
        if away not in TEAMS or home not in TEAMS:
            skipped += 1
            continue
        picks.append({
            "eventId": g.get("eventId"),
            "week": week,
            "seasonDate": season_date,
            "away": away,
            "home": home,
            "kickoffEt": g.get("kickoffEt"),
            "favorite": g.get("favorite"),
            "favoritePct": g.get("favoritePct"),
            "underdog": g.get("underdog"),
            "underdogPct": g.get("underdogPct"),
            "marketIds": g.get("marketIds", []),
        })

    if not picks:
        print(f"CONVEX_SYNC=failed: 0 NFL picks after filtering "
              f"({skipped} non-NFL skipped)", file=sys.stderr)
        return 0

    body = json.dumps({"picks": picks}).encode()
    # Use curl with a browser User-Agent: Cloudflare bot protection (error
    # 1010) blocks Python urllib on this endpoint, while curl works.
    try:
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as tf:
            tf.write(body)
            tf_path = tf.name
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "30", "-X", "POST", UPSERT_URL,
                 "-H", "Content-Type: application/json",
                 "-H", "User-Agent: Mozilla/5.0",
                 "--data", "@" + tf_path],
                capture_output=True, text=True, timeout=35
            )
            res = json.loads(result.stdout)
        finally:
            os.unlink(tf_path)
        if res.get("ok"):
            print(f"CONVEX_SYNC=ok: inserted={res.get('inserted')} "
                  f"updated={res.get('updated')} skipped_non_nfl={skipped}")
            return 0
        print(f"CONVEX_SYNC=failed: endpoint returned {res}", file=sys.stderr)
    except Exception as ex:
        print(f"CONVEX_SYNC=failed: {ex} (endpoint likely not deployed yet "
              f"-- JSON + tweet unaffected)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
