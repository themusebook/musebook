#!/bin/sh
# Run ON the clawd-connector machine (via smol_cloud.py exec --shell).
# Pulls the live 79-skill tarball and extracts it.
set -e
mkdir -p /workspace/clawd-connector/skills
cd /workspace/clawd-connector
curl -fsSL -o clawd-skills.tar.gz https://musebook.trade/clawd-skills.tar.gz
tar xzf clawd-skills.tar.gz -C skills
echo "skill dirs: $(ls skills | wc -l)"
test -f skills/clawd-live-bundle/SKILL.md && echo "canary: clawd-live-bundle present"
test -f skills/rh-bonded-launch/SKILL.md && echo "canary: rh-bonded-launch present"
