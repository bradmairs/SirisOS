# SirisOS Runtime Data

This directory contains persistent runtime data for the self-hosted SirisOS deployment.

The directory structure is tracked, but generated contents are ignored by Git.

- `postgres/` — PostgreSQL database files
- `logs/` — application logs
- `backups/` — future database and configuration backups
- `uploads/` — general user-uploaded files
- `standards/` — private engineering standards PDFs, metadata and locally extracted search indexes

Back up this directory together with `.env` to preserve a SirisOS installation.

Licensed standards under `data/standards` are private runtime content and must never be committed to the repository. Do not commit database files, logs, credentials, backups, uploads, or standards to Git.
