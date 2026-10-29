#!/usr/bin/env python3
"""Supermemory memory-layer client.

Calls https://api.supermemory.ai with the user-connected custom.supermemory
credential (Bearer header). Search memories/documents, ingest content, and
read container profiles.

Auth comes from the stored connector via dynamic_credentials; never pass or
print a raw key. urllib only (the credential surrogate substitutes on the
Python urllib path; curl/raw http.client go out unauthenticated).

Container tags (singular, ^[a-zA-Z0-9_:-]+$, max 100 chars, never cross-query):
  musebook:operator        Clawd<->operator memory (default for agent use)
  musebook:visitor:<uuid>  site chat visitors
  musebook:agent:<id>      first-party API agents
  musebook:docs            shared reference docs (superrag)

Examples:
  sm.py search --q "typesafe jev intent routing" --limit 5
  sm.py search --q "launch policy" --tag musebook:agent:abc123 --mode documents
  sm.py add --content "Jev routed the refund ticket to billing, conf 1.0" \\
      --metadata '{"source":"jev-loop"}'
  sm.py profile
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

BASE = os.environ.get("SUPERMEMORY_API_URL", "https://api.supermemory.ai").rstrip("/")
HOSTS = ("api.supermemory.ai",)
CREDENTIAL = "custom.supermemory"
DEFAULT_TAG = "musebook:operator"
TAG_RE = re.compile(r"^[a-zA-Z0-9_:-]+$")


def check_tag(tag):
    tag = (tag or "")[:100]
    if not tag or not TAG_RE.match(tag):
        print(f"Invalid containerTag {tag!r}: must match ^[a-zA-Z0-9_:-]+$ (<=100 chars).",
              file=sys.stderr)
        sys.exit(2)
    return tag


def post(path, body, timeout=30):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:2000]
        except Exception:
            detail = ""
        print(f"HTTP {e.code} on POST {path}: {detail}", file=sys.stderr)
        if e.code in (401, 403):
            print("Auth rejected: confirm the request carried the credential "
                  "(built via add_surrogate_to_request) before suspecting the key.",
                  file=sys.stderr)
        sys.exit(2)


def cmd_search(a):
    tag = check_tag(a.tag)
    body = {"q": a.q, "containerTag": tag, "searchMode": a.mode, "limit": a.limit}
    r = post("/v4/search", body)
    results = (r or {}).get("results") or []
    if a.compact:
        for m in results[:a.limit]:
            txt = m.get("content") or m.get("text") or m.get("summary") or ""
            print("- " + str(txt).replace("\n", " ")[:300])
    else:
        print(json.dumps(results, indent=2)[:6000])


def cmd_docs(a):
    body = {"q": a.q, "containerTag": "musebook:docs",
            "searchMode": "documents", "limit": a.limit}
    r = post("/v3/search", body)
    hits = (r or {}).get("results") or []
    out = []
    for hit in hits:
        for c in (hit.get("chunks") or []):
            txt = str((c or {}).get("content") or "").strip()
            if txt:
                out.append(txt[:600])
            if len(out) >= a.limit:
                break
        if len(out) >= a.limit:
            break
    if a.compact:
        for t in out:
            print("- " + t.replace("\n", " ")[:300])
    else:
        print(json.dumps(out, indent=2)[:6000])


def cmd_add(a):
    tag = check_tag(a.tag)
    content = a.content
    if a.stdin:
        content = sys.stdin.read()
    if not content or not content.strip():
        print("Nothing to ingest: empty content.", file=sys.stderr)
        sys.exit(2)
    body = {"content": content, "containerTag": tag,
            "taskType": a.task_type or "memory"}
    if a.custom_id:
        body["customId"] = a.custom_id
    if a.metadata:
        try:
            body["metadata"] = json.loads(a.metadata)
        except json.JSONDecodeError as e:
            print(f"Bad --metadata JSON: {e}", file=sys.stderr)
            sys.exit(2)
    r = post("/v3/documents", body, timeout=45)
    print(json.dumps(r, indent=2)[:2000] if not a.compact else "ingested ok")


def cmd_profile(a):
    tag = check_tag(a.tag)
    r = post("/v4/profile", {"containerTag": tag}, timeout=45)
    print(json.dumps(r, indent=2)[:4000] if not a.compact else
          json.dumps(r)[:1000])


def main():
    p = argparse.ArgumentParser(prog="sm.py", description="Supermemory memory-layer client")
    p.add_argument("--tag", default=DEFAULT_TAG, help="containerTag (default musebook:operator)")
    p.add_argument("--compact", action="store_true", help="terse output")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search memories or documents in a tag")
    s.add_argument("--q", required=True)
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--mode", default="memories", choices=["memories", "documents"])

    d = sub.add_parser("docs", help="search shared superrag docs (musebook:docs)")
    d.add_argument("--q", required=True)
    d.add_argument("--limit", type=int, default=3)

    ad = sub.add_parser("add", help="ingest content into a tag")
    ad.add_argument("--content", default="")
    ad.add_argument("--stdin", action="store_true")
    ad.add_argument("--custom-id", default="")
    ad.add_argument("--metadata", default="")
    ad.add_argument("--task-type", default="memory")

    pr = sub.add_parser("profile", help="read a container's profile")

    a = p.parse_args()
    {"search": cmd_search, "docs": cmd_docs, "add": cmd_add,
     "profile": cmd_profile}[a.cmd](a)


if __name__ == "__main__":
    main()
