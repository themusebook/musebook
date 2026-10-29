#!/usr/bin/env python3
"""SerpApi search CLI. Surrogate-authenticated against the user's custom.serpapi connector.

Usage:
  serp.py search --q "query" [--engine google] [--num 10] [--location "Austin, TX"]
                   [--gl us] [--hl en] [--raw]
  serp.py account            # quota / plan info (free, does not consume a search)
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
import dynamic_credentials as dc

BASE = "https://serpapi.com"
ALLOWED = ["serpapi.com"]
CRED = "custom.serpapi"


def get(path, params):
    query = urllib.parse.urlencode(params)
    url = f"{BASE}{path}?{query}"
    authed = dc.url_with_surrogate_query_param(url, CRED, allowed_hosts=ALLOWED)
    req = urllib.request.Request(authed, headers={"User-Agent": "clawd-serpapi-skill/1.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    return dc.read_json_response(resp)


def normalize(data):
    out = {"search_metadata": data.get("search_metadata", {}),
           "organic_results": [
               {"title": r.get("title"), "link": r.get("link"), "snippet": r.get("snippet"),
                "position": r.get("position"), "source": r.get("source")}
               for r in data.get("organic_results", [])],
           "answer_box": data.get("answer_box"),
           "knowledge_graph": data.get("knowledge_graph"),
           "ai_overview": data.get("ai_overview"),
           "related_questions": [
               {"question": q.get("question"), "link": q.get("link"), "snippet": q.get("snippet")}
               for q in data.get("related_questions", [])],
           "local_results": data.get("local_results"),
           "shopping_results": data.get("shopping_results"),
           }
    return {k: v for k, v in out.items() if v not in (None, [], {})}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search")
    s.add_argument("--q", required=True)
    s.add_argument("--engine", default="google")
    s.add_argument("--num", type=int, default=10)
    s.add_argument("--location")
    s.add_argument("--gl", default="us")
    s.add_argument("--hl", default="en")
    s.add_argument("--raw", action="store_true")

    sub.add_parser("account")

    args = ap.parse_args()
    try:
        if args.cmd == "search":
            params = {"engine": args.engine, "q": args.q, "num": args.num,
                      "gl": args.gl, "hl": args.hl, "output": "json"}
            if args.location:
                params["location"] = args.location
            data = get("/search.json", params)
            if "error" in data:
                print(json.dumps({"error": data["error"]}, indent=2))
                sys.exit(2)
            print(json.dumps(data if args.raw else normalize(data), indent=2, ensure_ascii=False))
        elif args.cmd == "account":
            print(json.dumps(get("/account.json", {}), indent=2))
    except dc.DynamicCredentialError as e:
        print(json.dumps({"error": f"auth: {e}"}))
        sys.exit(1)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(json.dumps({"error": f"http {e.code}", "body": body}))
        sys.exit(1)


if __name__ == "__main__":
    main()
