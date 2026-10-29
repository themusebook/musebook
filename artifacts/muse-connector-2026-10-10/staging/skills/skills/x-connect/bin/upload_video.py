#!/usr/bin/env python3
"""Chunked video upload to X API v2 + attach to a tweet.

STATUS (2026-09-17): video upload is NOT possible with the current credential.
X requires OAuth 1.0a for video (v1.1 chunked on upload.twitter.com returns
401 with OAuth2 bearer; v2 simple /2/media/upload rejects video/mp4 with 400).
The stored ``custom.x`` credential is OAuth2, so this script fails at upload.
Left in place for when an OAuth 1.0a credential becomes available.

Auth: stored ``custom.x`` OAuth2 credential via surrogate exchange.
Never prints or persists raw credentials.

Usage:
    upload_video.py --video file.mp4 --text "tweet text" [--reply-to <id>]
Prints JSON with tweet_id, tweet_url, reply info.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    ensure_allowed_url,
    read_json_response,
)
sys.path.insert(0, "/home/hatch/workspace/skills/x-connect/bin")
import tweet  # noqa: E402

API = "https://api.x.com"
ALLOWED = ("api.x.com", "api.twitter.com")
CHUNK = 1024 * 1024  # 1MB segments
MAX_TWEET = 280


def x_post_json(url: str, payload: dict) -> dict:
    ensure_allowed_url(url, ALLOWED)
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    add_surrogate_to_request(req, "custom.x", allowed_hosts=ALLOWED)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return read_json_response(resp)


def x_post_multipart(url: str, fields: dict[str, str], file_field: str,
                     filename: str, file_bytes: bytes, mime: str) -> dict:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
    ).encode()
    body += file_bytes + f'\r\n--{boundary}--\r\n'.encode()
    ensure_allowed_url(url, ALLOWED)
    req = urllib.request.Request(
        url, data=bytes(body), method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    add_surrogate_to_request(req, "custom.x", allowed_hosts=ALLOWED)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return read_json_response(resp)


def upload_video(path: str) -> str:
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    init = x_post_json(f"{API}/2/media/upload", {
        "command": "INIT", "media_type": mime,
        "media_category": "tweet_video", "total_bytes": size,
    })
    media_id = str((init.get("data") or {}).get("id") or "")
    if not media_id:
        raise RuntimeError(f"INIT failed: {json.dumps(init)[:300]}")
    with open(path, "rb") as f:
        idx = 0
        while True:
            seg = f.read(CHUNK)
            if not seg:
                break
            r = x_post_multipart(f"{API}/2/media/upload", {
                "command": "APPEND", "media_id": media_id,
                "segment_index": str(idx),
            }, "media", os.path.basename(path), seg, mime)
            if r.get("errors"):
                raise RuntimeError(f"APPEND {idx} failed: {json.dumps(r)[:300]}")
            idx += 1
    fin = x_post_json(f"{API}/2/media/upload",
                      {"command": "FINALIZE", "media_id": media_id})
    info = (fin.get("data") or {}).get("processing_info") or {}
    for _ in range(60):
        state = info.get("state")
        if state == "succeeded":
            break
        if state == "failed":
            raise RuntimeError(f"video processing failed: {json.dumps(fin)[:300]}")
        time.sleep(info.get("check_after_secs", 5) or 5)
        st = x_post_json(f"{API}/2/media/upload",
                         {"command": "STATUS", "media_id": media_id})
        info = (st.get("data") or {}).get("processing_info") or {}
    else:
        raise RuntimeError("video processing timed out")
    return media_id


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--reply-to")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if len(a.text) > MAX_TWEET:
        raise SystemExit(f"tweet too long: {len(a.text)} chars")
    if a.dry_run:
        print(json.dumps({"video": a.video, "text": a.text}, indent=2))
        return 0
    media_id = upload_video(a.video)
    payload = {"text": a.text, "media": {"media_ids": [media_id]}}
    if a.reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": a.reply_to}
    r = x_post_json(f"{API}/2/tweets", payload)
    tid = (r.get("data") or {}).get("id")
    if not tid:
        raise RuntimeError(f"tweet failed: {json.dumps(r)[:300]}")
    print(json.dumps({"tweet_id": tid,
                      "tweet_url": f"https://x.com/i/status/{tid}"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
