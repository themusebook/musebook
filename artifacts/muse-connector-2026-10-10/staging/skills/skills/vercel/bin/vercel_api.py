#!/usr/bin/env python3
"""Call api.vercel.com with the stored custom.vercel credential."""
import sys, os, json, urllib.request, urllib.parse
sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response
BASE = "https://api.vercel.com"
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="GET")
    ap.add_argument("--path", required=True)
    ap.add_argument("--params", default="{}")
    args = ap.parse_args()
    url = BASE + args.path
    params = json.loads(args.params)
    if params: url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=args.method, headers={"Accept": "application/json"})
    add_surrogate_to_request(req, "custom.vercel", allowed_hosts=["api.vercel.com"])
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(json.dumps(read_json_response(resp)))
main()
