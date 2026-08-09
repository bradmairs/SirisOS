# SirisOS Runtime Data

This directory contains persistent runtime data for the self-hosted SirisOS deployment.

The directory structure is tracked, but generated contents are ignored by Git.

- `postgres/` — PostgreSQL database files
- `logs/` — application logs
- `backups/` — future database and configuration backups
- `uploads/` — general user-uploaded files
- `standards/` — private engineering standards PDFs, metadata and locally extracted search indexes
- `knowledge/` — Obsidian vault SirisOS reads Knowledge notes from (mounted read-only)
- `app/` — atomic JSON record stores mounted at `/app/data` (projects, project context, saved calculations, SirisHydro query history) — see ADR 060

Back up this directory together with `.env` to preserve a SirisOS installation.

Licensed standards under `data/standards` are private runtime content and must never be committed to the repository. Do not commit database files, logs, credentials, backups, uploads, standards, knowledge notes, or app records to Git.
