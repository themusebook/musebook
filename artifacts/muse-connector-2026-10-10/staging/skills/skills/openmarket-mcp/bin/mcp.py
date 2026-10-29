#!/usr/bin/env python3
"""OpenMarket chart MCP client (Streamable HTTP).

Usage:
  mcp.py tools                      # list available tools
  mcp.py call <tool> ['{json}']     # call a tool, e.g. mcp.py call chart_status '{}'

Auth: the stored custom.openmarket-mcp agent token rides the Authorization:
Bearer header via authd surrogate exchange. Never prints the token.

Transport notes: uses curl (subprocess) rather than urllib — urllib stalls
through this host's egress proxy on mcp.openmarket.xyz. The hsurr surrogate
is passed to curl's argv without ever being printed or logged.

Follows the llms.txt connect flow: after the token is stored, call
chart_workspace_select (if a chart was named), chart_status, then chart_refresh.
"""
import sys
import os
import json
import subprocess
import tempfile

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    dynamic_credential_entry,
    ensure_allowed_url,
    DynamicCredentialError,
)

ENDPOINT = "https://mcp.openmarket.xyz/"
ALLOWED = ["mcp.openmarket.xyz"]
CRED = "custom.openmarket-mcp"


def _curl_jsonrpc(payload: dict, timeout: int = 40) -> dict:
    """POST one JSON-RPC message via curl; return the parsed reply."""
    try:
        entry = dynamic_credential_entry(CRED)
        ensure_allowed_url(ENDPOINT, ALLOWED)
    except DynamicCredentialError as e:
        print(f"AUTH ERROR: {e}", file=sys.stderr)
        sys.exit(3)
    surrogate = str(entry["surrogate"]).strip()
    placement = entry.get("placement")
    if placement == "bearer_header":
        auth_header = f"Authorization: Bearer {surrogate}"
    elif isinstance(placement, dict) and isinstance(placement.get("custom_header"), str):
        auth_header = f"{placement['custom_header']}: {surrogate}"
    else:
        print(f"AUTH ERROR: unsupported credential placement: {placement!r}",
              file=sys.stderr)
        sys.exit(3)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        body_path = f.name
    hdr_path = body_path + ".headers"
    out_path = body_path + ".out"
    try:
        proc = subprocess.run(
            ["curl", "-sS", "-m", str(timeout), "-X", "POST", ENDPOINT,
             "-H", "Content-Type: application/json",
             "-H", "Accept: application/json, text/event-stream",
             "-H", auth_header,
             "-D", hdr_path, "-o", out_path, "-w", "%{http_code}",
             "--data-binary", f"@{body_path}"],
            capture_output=True, text=True, timeout=timeout + 10)
    finally:
        os.unlink(body_path)
    if proc.returncode != 0:
        print(f"REQUEST ERROR: curl failed: {proc.stderr.strip()[:500]}",
              file=sys.stderr)
        sys.exit(1)
    http_code = proc.stdout.strip()

    try:
        with open(out_path, "rb") as f:
            raw = f.read()
        os.unlink(out_path)
        headers = open(hdr_path).read() if os.path.exists(hdr_path) else ""
        if os.path.exists(hdr_path):
            os.unlink(hdr_path)
    except OSError as e:
        print(f"REQUEST ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    text = raw.decode("utf-8", "replace")
    if not text.strip():
        # Notifications (no id) and some servers answer 202 with empty body.
        return {"ok": True, "http_code": http_code}
    if "text/event-stream" in headers:
        messages = []
        for line in text.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk and chunk != "[DONE]":
                    try:
                        messages.append(json.loads(chunk))
                    except json.JSONDecodeError:
                        pass
        if not messages:
            print("MCP ERROR: empty SSE stream", file=sys.stderr)
            sys.exit(1)
        return messages[-1]
    if not text.strip():
        print("MCP ERROR: empty response body", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"MCP ERROR: non-JSON reply: {text[:500]}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    cmd = sys.argv[1]

    # MCP handshake: initialize, then notifications/initialized.
    init = _curl_jsonrpc({
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "clawd", "version": "1.0"}}})
    if init.get("error"):
        print(f"MCP ERROR on initialize: {json.dumps(init['error'])[:500]}",
              file=sys.stderr)
        return 1
    _curl_jsonrpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

    if cmd == "tools":
        result = _curl_jsonrpc(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    elif cmd == "call":
        if len(sys.argv) < 3:
            print("usage: mcp.py call <tool> ['{json args}']", file=sys.stderr)
            return 2
        tool = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        result = _curl_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": tool, "arguments": args}})
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2

    if isinstance(result, dict) and result.get("error"):
        print(f"MCP ERROR: {json.dumps(result['error'])[:1000]}",
              file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2)[:200000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
