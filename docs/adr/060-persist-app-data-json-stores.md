# ADR 060 — Persist the `/app/data` JSON record stores

## Status

Accepted.

## Context

Several features persist state as an atomic JSON file directly under `/app/data` inside the container: Projects (`projects.json`, ADR 049), current project context (`project-context.json`, ADR 051), saved Engineering calculations (`engineering-calculations.json`, ADR 055), and now SirisHydro query history (`sirishydro-history.json`, ADR 059). Each of those ADRs describes the atomic-write mechanism (temp file + rename) but none of them is about deployment, and `docker-compose.yml` was never updated to actually persist the directory those files live in. Only `/app/data/standards` and `/app/data/knowledge` had bind mounts. Every other file directly under `/app/data` lived in the container's writable layer, which `make up`'s `docker compose up --build` discards and recreates on every rebuild — so projects, saved calculations, and (as of this ADR) SirisHydro's history were silently wiped on every `git pull && make up`, the documented standard deployment workflow.

This was found while confirming SirisHydro's new query history (ADR 059) — explicitly framed as a step toward "SirisHydro as an agent with memory" — would actually survive a normal deploy. It wouldn't have.

## Decision

`docker-compose.yml` gains a `./data/app:/app/data` bind mount, added before the existing more-specific `/app/data/standards` and `/app/data/knowledge` mounts so those continue to override their own subpaths (standards stays read-write, knowledge stays read-only) exactly as before — Docker mounts layer in listing order, so a later, more specific mount always wins for its own path. `data/app/` is a new host directory, tracked in `.gitignore`/`.gitkeep` the same way `data/postgres`, `data/logs`, `data/backups` and `data/uploads` already are; `make up` creates it alongside them.

A dedicated directory (`data/app`) rather than mounting the whole `data/` tree onto `/app/data` was chosen deliberately: it keeps the sirisos container's view of `/app/data` scoped to what it actually owns, rather than also exposing sibling directories like `data/postgres` (owned by the separate `postgres` service) inside the app container's filesystem.

## Consequences

- Projects, project context, saved calculations, and SirisHydro history now survive `git pull && make up`, matching the persistence guarantee every ADR that introduced these stores already implied but didn't deliver.
- Any future feature that persists a bare JSON/atomic-write file directly under `/app/data` (not `/app/data/<subdir>`) is covered by this mount automatically — no compose change needed per feature.
- Existing production data that was already lost to this gap is not recoverable by this fix; it only prevents further loss going forward.
- `data/app/` should be backed up alongside `data/postgres`, `data/standards` and `.env` per `data/README.md`.
