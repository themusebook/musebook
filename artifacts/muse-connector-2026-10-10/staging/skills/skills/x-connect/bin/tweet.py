#!/usr/bin/env python3
"""Post the pump.fun top-10 pulse as a tweet with generated art.

Reads a pumpfun-pulse digest (``pulse.py --top 10 --json-only``) from
--pulse-json, uploads --image via X API v2 media upload, and posts a tweet
with the image attached. Text fits 280 chars; the image carries the full
top-10 leaderboard.

Auth: stored ``custom.x`` OAuth2 credential via surrogate exchange.
Never prints or persists raw credentials.

Usage:
    tweet.py --pulse-json digest.json --image art.png [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    ensure_allowed_url,
    read_json_response,
)

API = "https://api.x.com"
ALLOWED = ("api.x.com", "api.twitter.com")
MAX_TWEET = 280
MAX_IMG_BYTES = 4_700_000

# Substrings that must never appear in a tweet or leaderboard image.
# Token names are copied verbatim from on-chain data; screen them here.
SLUR_BLOCKLIST = (
    "nigger", "nigga", "chink", "spic", "kike", "faggot", "retard",
    "tranny", "wetback", "beaner", "gook", "raghead",
)


# Word-boundary matching: catches standalone slurs but not innocent
# substrings (e.g. "spic" inside a domain name like "jeffspicoli").
import re as _re
_SLUR_RE = _re.compile(r"\b(" + "|".join(_re.escape(s) for s in SLUR_BLOCKLIST) + r")\b")


def is_clean(text: str) -> bool:
    return not _SLUR_RE.search((text or "").lower())


def sanitize_tokens(tokens: list[dict]) -> list[dict]:
    """Drop tokens whose name/symbol contains blocklisted slurs.

    Returns the cleaned list; logs what was removed so runs stay auditable.
    """
    clean, removed = [], []
    for t in tokens:
        if is_clean(t.get("name", "")) and is_clean(t.get("symbol", "")):
            clean.append(t)
        else:
            removed.append(t.get("mint", "?"))
    for m in removed:
        print(f"sanitized: dropped token {m} (blocklisted name/symbol)", file=sys.stderr)
    return clean


def load_digest(path: str) -> tuple[list[dict], list[dict]]:
    with open(path) as f:
        data = json.load(f)
    top = data.get("top") or []
    # Sanitize before anything public (tweet text, leaderboard art) uses names.
    tokens = sanitize_tokens(top[:10])
    trending = []
    for tr in data.get("trending") or []:
        if is_clean(tr.get("name", "")) and is_clean(tr.get("symbol", "")):
            trending.append(tr)
    return tokens, trending


def short_name(name: str, limit: int = 16) -> str:
    name = " ".join(name.split())
    return name if len(name) <= limit else name[: limit - 1].rstrip() + "…"


def compose(tokens: list[dict], trending: list[dict] | None = None) -> str:
    header = "⚡ Top 10 pump.fun launches 🦞"
    footer = "powered by $CLAWD"
    # Trending line (24h, BirdEye): computed first so the list reserves room.
    # Symbols stay cashtag-free so $CLAWD keeps the post's single cashtag.
    trending = trending or []
    top_tr = [t["symbol"].lstrip("$")[:10] for t in trending[:3]]
    tr_line = f"🔥 Trending 24h: {', '.join(top_tr)}" if top_tr else ""
    lines = [header]
    shown = 0
    for i, t in enumerate(tokens, 1):
        # X allows max ONE cashtag per post: keep $CLAWD in the footer, so token
        # symbols are listed WITHOUT the $ prefix.
        entry = f"{i}. {short_name(t['name'])} ({t['symbol'].lstrip('$')[:10]})"
        candidate = "\n".join(lines + [entry])
        reserve = len(f"\n+{len(tokens) - i} more in the chart 👇\n{footer}")
        if tr_line:
            reserve += len("\n" + tr_line)
        if len(candidate) + reserve > MAX_TWEET - 5:
            break
        lines.append(entry)
        shown = i
    rest = len(tokens) - shown
    if rest > 0:
        lines.append(f"+{rest} more in the chart 👇")
    if tr_line:
        lines.append(tr_line)
    lines.append(footer)
    return "\n".join(lines)[:MAX_TWEET]


def prepare_image(path: str) -> tuple[bytes, str]:
    with open(path, "rb") as f:
        raw = f.read()
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/png"
    if len(raw) > MAX_IMG_BYTES:
        try:
            from PIL import Image
            import io

            img = Image.open(path)
            for q in (88, 80, 72, 64, 55):
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "JPEG", quality=q)
                if len(buf.getvalue()) <= MAX_IMG_BYTES:
                    return buf.getvalue(), "image/jpeg"
            raise RuntimeError("image still too large after re-encode")
        except ImportError:
            raise RuntimeError(f"image is {len(raw)} bytes; exceeds 5MB X limit")
    return raw, mime


def x_request(method: str, url: str, payload: dict | None = None,
             _retry_auth: bool = True) -> dict:
    ensure_allowed_url(url, ALLOWED)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    add_surrogate_to_request(req, "custom.x", allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:600]
        except Exception:
            body = "<unreadable>"
        # The custom.x surrogate occasionally serves an app-only token on
        # one attempt; POST /2/tweets then 403s with "Unsupported Authentication"
        # even though user context is healthy moments later. Retry once after a
        # short wait (fresh surrogate exchange) before giving up. Safe: an
        # explicit 403 means no tweet was posted, so no duplicate risk.
        if (e.code == 403 and _retry_auth
                and "Unsupported Authentication" in body):
            import time
            time.sleep(15)
            return x_request(method, url, payload, _retry_auth=False)
        raise RuntimeError(f"X API {method} {url} -> HTTP {e.code}: {body}")


def upload_media(image_path: str) -> str:
    raw, mime = prepare_image(image_path)
    payload = {
        "media": base64.b64encode(raw).decode("ascii"),
        "media_category": "tweet_image",
        "media_type": mime,
        "shared": False,
    }
    resp = x_request("POST", f"{API}/2/media/upload", payload)
    media_id = (resp.get("data") or {}).get("id")
    if not media_id:
        raise RuntimeError(f"media upload failed: {json.dumps(resp)[:300]}")
    # X sometimes returns the id wrapped in literal quote characters; strip them.
    return str(media_id).strip().strip('"').strip("'")


def post_tweet(text: str, media_ids: list[str] | None) -> dict:
    payload: dict = {"text": text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}
    return x_request("POST", f"{API}/2/tweets", payload)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulse-json")
    ap.add_argument("--text")
    ap.add_argument("--image", required=False, default=None, action="append",
                    help="Attach an image; repeat for up to 4 images.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.text:
        text = args.text.strip()
        # X wraps every URL in t.co, so each URL counts as 23 chars on X.
        weighted = re.sub(r"https?://\S+", "x" * 23, text)
        if len(weighted) > MAX_TWEET:
            print(f"text is {len(weighted)} weighted chars; exceeds {MAX_TWEET}", file=sys.stderr)
            return 1
    elif args.pulse_json:
        tokens, trending = load_digest(args.pulse_json)
        if not tokens:
            print("no qualifying launches in window; nothing to tweet")
            return 0
        text = compose(tokens, trending)
    else:
        print("need --text or --pulse-json", file=sys.stderr)
        return 1
    print(f"--- tweet ({len(text)} chars) ---")
    print(text)
    print("-------------------------------")
    if args.dry_run:
        print("dry run: not uploading, not posting")
        return 0

    images = args.image or []
    if len(images) > 4:
        print("X allows max 4 images per tweet", file=sys.stderr)
        return 1
    media_ids = [upload_media(p) for p in images] or None
    if media_ids:
        print(f"media_ids: {media_ids}")
    resp = post_tweet(text, media_ids)
    tid = (resp.get("data") or {}).get("id")
    if not tid:
        print(f"tweet failed: {json.dumps(resp)[:500]}", file=sys.stderr)
        return 1
    print(f"posted: https://x.com/i/status/{tid}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
