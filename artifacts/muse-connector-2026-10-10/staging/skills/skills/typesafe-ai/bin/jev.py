#!/usr/bin/env python3
"""Jev (TypeSafe System One) typed-judgment client.

Calls POST https://api.typesafe.ai/v1/systemone with the user-connected
custom.typesafe credential. Asks one or more typed questions (choice / score /
noul) against a state string; Jev returns structured answers with
probabilities that code can branch on.

Auth comes from the stored connector via dynamic_credentials; never pass or
print a raw key. urllib only (the credential surrogate substitutes on the
Python urllib path; curl/raw http.client go out unauthenticated).

Examples:
  jev.py ask --state "Refund my order, it's been 3 weeks!" \\
      --questions '{"urgency": {"type": "noul", "instructions": "Does this message express urgency?"}}'

  jev.py ask --state-file ticket.txt --questions-file questions.json --compact

  echo "long state text" | jev.py ask --stdin \\
      --questions '{"dept": {"type": "choice", "instructions": "Which team should handle this", "criteria": {"billing": "payment issues", "technical": "bugs"}}}'
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

BASE = os.environ.get("TYPESAFE_API_URL", "https://api.typesafe.ai").rstrip("/")
HOSTS = ("api.typesafe.ai",)
CREDENTIAL = "custom.typesafe"
ENDPOINT = "/v1/systemone"


def call_api(state, questions, model="jev-latest"):
    url = f"{BASE}{ENDPOINT}"
    body = {"state": state, "model": model, "questions": questions}
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:2000]
        except Exception:
            detail = ""
        print(f"HTTP {e.code} on POST {ENDPOINT}: {detail}", file=sys.stderr)
        if e.code in (401, 403):
            print("Auth rejected: confirm the request carried the credential "
                  "(built via add_surrogate_to_request) before suspecting the key.",
                  file=sys.stderr)
        sys.exit(2)


def compact_summary(answers):
    lines = []
    for qid, ans in answers.items():
        qtype = ans.get("type", "?")
        if qtype == "choice":
            lines.append(f"{qid}: choice={ans.get('choice')} "
                         f"conf={ans.get('confidence')}")
        elif qtype == "score":
            lines.append(f"{qid}: score={ans.get('score')} "
                         f"conf={ans.get('confidence')}")
        elif qtype == "noul":
            lines.append(f"{qid}: noul={ans.get('noul')}")
        else:
            lines.append(f"{qid}: {json.dumps(ans)}")
    return "\n".join(lines)


def load_state(a):
    if a.stdin:
        return sys.stdin.read()
    if a.state_file:
        with open(a.state_file) as f:
            return f.read()
    return a.state


def load_questions(a):
    if a.questions_file:
        with open(a.questions_file) as f:
            return json.load(f)
    try:
        return json.loads(a.questions)
    except json.JSONDecodeError as e:
        print(f"Invalid --questions JSON: {e}", file=sys.stderr)
        sys.exit(2)


def cmd_ask(a):
    state = load_state(a)
    if not state or not state.strip():
        print("Empty state: pass --state, --state-file, or --stdin.", file=sys.stderr)
        sys.exit(2)
    questions = load_questions(a)
    if not isinstance(questions, dict) or not questions:
        print("--questions must be a non-empty JSON object of question definitions.",
              file=sys.stderr)
        sys.exit(2)
    resp = call_api(state, questions, model=a.model)
    answers = resp.get("answers", {})
    if a.compact:
        print(compact_summary(answers))
    else:
        print(json.dumps(answers, indent=2))
    if a.usage and "usage" in resp:
        print(json.dumps({"usage": resp["usage"]}, indent=2), file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description="Ask Jev (TypeSafe System One) typed questions.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="Ask typed questions against a state.")
    src = ask.add_mutually_exclusive_group(required=True)
    src.add_argument("--state", help="State text to judge.")
    src.add_argument("--state-file", help="File containing the state text.")
    src.add_argument("--stdin", action="store_true", help="Read state from stdin.")
    qsrc = ask.add_mutually_exclusive_group(required=True)
    qsrc.add_argument("--questions", help="JSON object of question definitions.")
    qsrc.add_argument("--questions-file", help="JSON file of question definitions.")
    ask.add_argument("--model", default="jev-latest", help="Model id (default: jev-latest).")
    ask.add_argument("--compact", action="store_true", help="One-line summary per question.")
    ask.add_argument("--usage", action="store_true", help="Print token usage to stderr.")
    ask.set_defaults(func=cmd_ask)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
