#!/usr/bin/env python3
"""Pin a directory to Pinata as a single IPFS directory object.

Usage:
    PINATA_JWT=<jwt> python3 pin_directory.py <dir> <wrap_name>

Builds one multipart request to POST /pinning/pinFileToIPFS with every file
under <dir>, using relative paths wrapped under <wrap_name>/ so the result is
a browsable IPFS directory. Returns the root IpfsHash.

Uses urllib (respects https_proxy env) since direct outbound HTTPS is blocked.
Auth: PINATA_JWT env var (transient). Restricted to api.pinata.cloud.
"""
import io
import json
import mimetypes
import os
import sys
import urllib.request

API = "https://api.pinata.cloud"
UA = "clawd-pinata/1.0"


def build_body(dir_path, wrap_name):
    boundary = "----MusebookPinDir" + os.urandom(8).hex()
    buf = io.BytesIO()

    files = []
    for root, _dirs, filenames in os.walk(dir_path):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, dir_path).replace(os.sep, "/")
            files.append((full, f"{wrap_name}/{rel}"))
    files.sort(key=lambda x: x[1])

    for full, arcname in files:
        ctype = mimetypes.guess_type(arcname)[0] or "application/octet-stream"
        buf.write(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{arcname}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n"
            ).encode()
        )
        with open(full, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                buf.write(chunk)
        buf.write(b"\r\n")

    meta = json.dumps({"name": wrap_name}).encode()
    buf.write(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="pinataMetadata"\r\n'
            "Content-Type: application/json\r\n\r\n"
        ).encode()
    )
    buf.write(meta + b"\r\n")

    opts = json.dumps({"cidVersion": 1}).encode()
    buf.write(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="pinataOptions"\r\n'
            "Content-Type: application/json\r\n\r\n"
        ).encode()
    )
    buf.write(opts + b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return boundary, buf.getvalue(), len(files)


def main():
    if len(sys.argv) < 3:
        print("usage: pin_directory.py <dir> <wrap_name>", file=sys.stderr)
        sys.exit(2)
    dir_path, wrap_name = sys.argv[1], sys.argv[2]

    jwt = os.environ.get("PINATA_JWT", "").strip()
    if not jwt:
        print("PINATA_JWT env var required", file=sys.stderr)
        sys.exit(2)

    boundary, body, nfiles = build_body(dir_path, wrap_name)
    print(f"uploading {nfiles} files, {len(body)/1e6:.1f} MB ...", file=sys.stderr, flush=True)

    req = urllib.request.Request(
        API + "/pinning/pinFileToIPFS",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            raw = resp.read()
            print(json.dumps({"http": resp.status, "files": nfiles,
                              "body": json.loads(raw.decode())}, indent=2))
    except urllib.error.HTTPError as e:
        print(json.dumps({"http": e.code, "error": e.read()[:500].decode("utf-8", "replace")}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
