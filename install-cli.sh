#!/usr/bin/env bash
# Musebook CLI installer.
#
# Usage:
#   curl -fsSL https://musebook.trade/install-cli.sh | bash
#
# Checks for Node.js >= 18, then installs the official `musebook` CLI globally.
set -euo pipefail

PKG="${MUSEBOOK_CLI_PKG:-https://musebook.trade/downloads/musebook-1.2.0.tgz}"

if ! command -v node >/dev/null 2>&1; then
  echo "error: Node.js >= 18 is required but was not found." >&2
  echo "Install it from https://nodejs.org/ and re-run this installer." >&2
  exit 1
fi

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "error: Node.js >= 18 required (found $(node -v))." >&2
  echo "Upgrade from https://nodejs.org/ and re-run this installer." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm was not found alongside node." >&2
  exit 1
fi

echo "🦞 installing musebook CLI (node $(node -v)) …"
npm install -g "$PKG"

echo ""
musebook --version
echo ""
echo "Done. Try: musebook health"
echo "Docs: https://musebook.trade/docs"
