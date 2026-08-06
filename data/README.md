# SirisOS Runtime Data

This directory contains persistent runtime data for the self-hosted SirisOS deployment.

The directory structure is tracked, but generated contents are ignored by Git.

- `postgres/` — PostgreSQL database files
- `logs/` — application logs
- `backups/` — future database and configuration backups
- `uploads/` — future user-uploaded files

Back up this directory together with `.env` to preserve a SirisOS installation.

Do not commit database files, logs, credentials, backups, or uploads to Git.
