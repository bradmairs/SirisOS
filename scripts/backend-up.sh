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

mkdir -p data/postgres data/logs data/backups data/uploads

echo "Starting SirisOS backend services..."
docker compose up --build -d

echo "Waiting for the API to become healthy..."
for attempt in {1..60}; do
  if curl --fail --silent http://localhost:8000/health >/dev/null 2>&1; then
    echo "SirisOS API is healthy at http://localhost:8000"
    echo "API documentation: http://localhost:8000/docs"
    exit 0
  fi
  sleep 2
done

echo "The API did not become healthy. Recent logs:" >&2
docker compose logs --tail=100 api >&2
exit 1
