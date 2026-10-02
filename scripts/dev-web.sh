#!/usr/bin/env bash
set -Eeuo pipefail

# Vite dev server for apps/web with hot reload, proxying /api to the running
# SirisOS container (or any SIRISOS_API_URL).
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/apps/web"

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 20+ (npm) is required but was not found in PATH." >&2
  exit 1
fi

PORT="$(grep -E '^SIRISOS_PORT=' "$ROOT_DIR/.env" 2>/dev/null | tail -1 | cut -d= -f2 || true)"
export SIRISOS_API_URL="${SIRISOS_API_URL:-http://localhost:${PORT:-8094}}"

bash "$ROOT_DIR/scripts/backend-up.sh"

cd "$WEB_DIR"
[[ -d node_modules ]] || npm ci
echo "API: ${SIRISOS_API_URL}"
exec npm run dev
