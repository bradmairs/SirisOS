# ADR 039 — Unified SirisOS application container

## Status
Accepted

## Context
SirisOS previously deployed the Flutter web frontend (`sirisos-web`) and FastAPI backend (`sirisos-api`) as separate containers. This created two application containers, required the frontend to be compiled with a server-specific API URL, and exposed the API separately on port 8000.

The goal is to simplify self-hosted deployment without collapsing infrastructure isolation for PostgreSQL, Docker socket access or host metrics.

## Decision
- Build Flutter and FastAPI into one production `sirisos` application image.
- Run Nginx and Uvicorn in that image under Supervisor.
- Nginx serves Flutter on port 6464 and reverse-proxies `/api/*`, `/health`, `/docs`, `/openapi.json` and `/redoc` to Uvicorn on loopback port 8000.
- Production Flutter resolves the API from the browser's current origin, removing the server-IP compile-time dependency.
- `SIRISOS_API_URL` remains available as a compile-time override for local Flutter development.
- The container healthcheck calls `/health` through Nginx so both the public web/proxy layer and FastAPI must be reachable before the application is healthy.
- Preserve OCRmyPDF/Tesseract in the unified application image for the private Engineering Standards Library.
- Keep PostgreSQL, docker-socket-proxy and node-exporter as separate containers because they have different lifecycle, persistence, privilege and host-access boundaries.
- Do not expose Uvicorn's loopback port from the production Compose stack; the public application/API surface is port 6464.

## Consequences
The normal deployment has one SirisOS application container and three infrastructure containers. Moving SirisOS to a different host/IP no longer requires rebuilding Flutter with a new API address. Application logs are consolidated under `docker compose logs sirisos`, while database and host-access isolation remain intact.
