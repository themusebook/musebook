#!/usr/bin/env python3
"""Monday resolution cron for the Sunday NFL prediction board.

For every unresolved nfl_picks doc (via the worker-proxied endpoint):
  1. Fetch the game's markets with jup_predict.py event-markets <eventId>.
  2. Determine the winner from the resolved moneyline markets.
  3. POST the result to /api/v1/nfl/picks/resolve (recomputes the week's
     nfl_records automatically).

A game whose markets are not yet resolved is left alone (logged, exit 0);
a later re-run picks it up. Read-only market data; no trades, no signing.
"""
import sys
import json
import os
import subprocess
import urllib.request

JUP = "/home/hatch/workspace/skills/jupiter/bin/jup_predict.py"
BASE = "https://musebook.trade/api/v1/nfl/picks"
INGEST_SECRET_FILE = os.path.expanduser("~/workspace/musebook/convex/.ingest_secret")


def ingest_secret():
    """Read the shared ingest secret at runtime (0600 file, never logged)."""
    try:
        with open(INGEST_SECRET_FILE) as f:
            return f.read().strip() or None
    except OSError:
        return None


def jup(*args):
    r = subprocess.run(["python3", JUP] + list(args),
                       capture_output=True, text=True, timeout=90)
    return json.loads(r.stdout)


def get(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def post(path, body):
    # The resolve write is gated worker-side (2026-09-28 fix): present the
    # shared ingest secret as a Bearer token. The worker never honors a
    # client-supplied x-worker-secret.
    headers = {"Content-Type": "application/json"}
    sec = ingest_secret()
    if sec:
        headers["Authorization"] = "Bearer " + sec
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def determine_winner(event_id):
    """Return (winner_team, detail) or (None, reason) if not resolved yet."""
    d = jup("event-markets", event_id)
    mkts = d.get("data", d.get("markets", []))
    team_mkts = [m for m in mkts
                 if m.get("sportsMarketType") == "moneyline"
                 and (m.get("title") or "").strip()]
    if not team_mkts:
        return None, "no moneyline markets"
    winners = []
    unresolved = 0
    for m in team_mkts:
        title = (m.get("title") or "").strip()
        status = (m.get("status") or "").lower()
        result = m.get("result")
        if status in ("resolved", "closed", "settled"):
            r = result
            if isinstance(r, str):
                rl = r.strip().lower()
                if rl in ("yes", "true", "1", title.lower(), "winner"):
                    winners.append(title)
                elif rl in ("no", "false", "0", "loser"):
                    continue  # loser
                else:
                    unresolved += 1  # ambiguous resolved result
            elif r is True:
                winners.append(title)
            elif r is False:
                continue
            else:
                unresolved += 1
        else:
            unresolved += 1
    if len(winners) == 1 and unresolved == len(team_mkts) - 1:
        return winners[0], "resolved"
    if len(winners) == 0:
        return None, "not yet resolved"
    return None, f"ambiguous results: {winners}"


def main():
    try:
        res = get(BASE + "/unresolved")
    except Exception as ex:
        print(f"RESOLVE=failed: cannot fetch unresolved picks: {ex}",
              file=sys.stderr)
        return 1
    picks = res.get("picks", []) if res.get("ok") else []
    print(f"RESOLVE: {len(picks)} unresolved pick(s)")
    resolved = skipped = errors = 0
    for p in picks:
        eid = p["eventId"]
        week = p["week"]
        fav = p.get("favorite", "?")
        try:
            winner, detail = determine_winner(eid)
        except Exception as ex:
            print(f"  {eid}: market fetch failed: {ex}", file=sys.stderr)
            errors += 1
            continue
        if winner is None:
            print(f"  {eid} ({p.get('away')} @ {p.get('home')}): {detail} "
                  f"-- leaving unresolved")
            skipped += 1
            continue
        try:
            r = post("/resolve", {"eventId": eid, "week": week,
                                  "winner": winner})
            if r.get("ok"):
                hit = "HIT" if r.get("hit") else "miss"
                print(f"  {eid}: {p.get('away')} @ {p.get('home')} -> "
                      f"{winner} (fav: {fav}) [{hit}]")
                resolved += 1
            else:
                print(f"  {eid}: resolve endpoint returned {r}",
                      file=sys.stderr)
                errors += 1
        except Exception as ex:
            print(f"  {eid}: resolve POST failed: {ex}", file=sys.stderr)
            errors += 1
    print(f"RESOLVE: done resolved={resolved} skipped={skipped} "
          f"errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
