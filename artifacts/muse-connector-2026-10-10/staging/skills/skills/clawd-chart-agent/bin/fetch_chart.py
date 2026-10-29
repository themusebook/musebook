#!/usr/bin/env python3
"""Download a chart image URL to the local cache and print the path.

Usage:
    fetch_chart.py --url <image_url> [--name <label>]
"""
from __future__ import annotations

import argparse
import imghdr
import os
import time
import urllib.request

CACHE = os.path.expanduser("~/workspace/chart-agent/charts")
MAX_BYTES = 20_000_000


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", default="chart")
    a = ap.parse_args(argv)

    if not (a.url.startswith("https://") or a.url.startswith("http://")):
        raise SystemExit("URL must start with http(s)://")

    os.makedirs(CACHE, exist_ok=True)
    req = urllib.request.Request(a.url, headers={"User-Agent": "clawd-chart-agent/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise SystemExit("image too large (>20MB)")
    if not raw:
        raise SystemExit("empty response")

    kind = imghdr.what(None, raw)
    if kind not in ("png", "jpeg", "gif", "webp"):
        raise SystemExit(f"not a supported image (detected: {kind})")

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in a.name)[:40] or "chart"
    path = os.path.join(CACHE, f"{safe}-{int(time.time())}.{ 'jpg' if kind == 'jpeg' else kind}")
    with open(path, "wb") as f:
        f.write(raw)
    print(path)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
