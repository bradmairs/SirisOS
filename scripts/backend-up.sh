#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

PORT="$(grep -E '^SIRISOS_PORT=' .env | tail -1 | cut -d= -f2 || true)"
PORT="${PORT:-8094}"

mkdir -p data/postgres data/logs data/standards data/app

echo "Starting SirisOS application and backend dependencies..."
docker compose up --build -d --remove-orphans sirisos

echo "Waiting for SirisOS to become healthy..."
for attempt in {1..60}; do
  if curl --fail --silent http://localhost:${PORT}/health >/dev/null 2>&1; then
    echo "SirisOS backend is healthy via http://localhost:${PORT}"
    echo "API documentation: http://localhost:${PORT}/docs"
    exit 0
  fi
  sleep 2
done

echo "SirisOS did not become healthy. Recent logs:" >&2
docker compose logs --tail=100 sirisos >&2
exit 1
