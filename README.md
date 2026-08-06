# SirisOS

SirisOS is a self-hosted personal operating system that brings together homelab monitoring, health and gym tracking, productivity, engineering tools, media services, knowledge management, and AI assistants.

## Initial stack

- Flutter frontend
- FastAPI backend
- PostgreSQL
- Docker Compose
- Restricted Docker socket proxy
- Ollama integration planned

## Repository layout

```text
apps/           Application code
data/           Persistent runtime data stored beside the Compose file
modules/        Feature modules
docs/           Project documentation
infrastructure/ Deployment and service configuration
```

## Current capabilities

- Responsive Flutter dashboard
- FastAPI dashboard API
- Live Docker container monitoring
- PostgreSQL service
- Self-contained relative data directories
- Restricted Docker socket proxy

## Development

Copy the example environment file, then start the stack:

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.

Persistent PostgreSQL files and application logs are stored under `./data/`. Back up the `data` directory and `.env` file to preserve the installation.

## Migrating from the previous named volume

The current Compose file uses `./data/postgres` rather than the former `sirisos_postgres_data` named volume. Existing deployments should export or copy their PostgreSQL data before removing the old volume. For a new development installation with no important data, simply rebuild the stack.

## Docker access

The API does not mount the host Docker socket directly. A dedicated socket proxy exposes only the read-only Docker endpoints required for monitoring containers. The proxy still mounts `/var/run/docker.sock` because that socket belongs to the host and cannot be stored inside the repository.
