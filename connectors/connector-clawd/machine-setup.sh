#!/bin/sh
# Optional developer full-pack install; not part of the submitted Muse tools.
set -eu
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
curl -fsSL https://musebook.trade/clawd-skills.tar.gz -o "$workdir/clawd-skills.tar.gz"
curl -fsSL https://musebook.trade/clawd-skills-manifest.json -o "$workdir/manifest.json"
python3 - "$workdir" <<'VERIFY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'manifest.json').read_text())
data = (root / 'clawd-skills.tar.gz').read_bytes()
assert hashlib.sha256(data).hexdigest() == manifest['sha256'], 'Archive checksum mismatch'
assert len(data) == manifest['bytes'], 'Archive byte size mismatch'
VERIFY
mkdir -p /workspace/clawd-connector/skills
tar xzf "$workdir/clawd-skills.tar.gz" --strip-components=1 -C /workspace/clawd-connector/skills
printf '%s\n' 'Developer skills installed; no account or transaction permission was granted.'
