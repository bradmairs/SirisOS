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
scripts/        Development helper scripts
```

## Current capabilities

- Responsive Flutter dashboard
- Functional Dashboard, Homelab, Gym, and Siris navigation
- Live Docker container monitoring
- FastAPI dashboard and Homelab APIs
- PostgreSQL service
- Self-contained relative data directories
- Restricted Docker socket proxy

## Prerequisites

Install the following before starting development:

- Docker with Docker Compose v2
- Flutter with Chrome/web support
- GNU Make
- curl

Check Flutter with:

```bash
flutter doctor
flutter devices
```

## One-command web development

From the repository root, run:

```bash
make dev
```

This command:

1. Creates `.env` from `.env.example` when needed.
2. Creates the relative `data/` directories.
3. Builds and starts PostgreSQL, the Docker socket proxy, and FastAPI.
4. Waits for the API health endpoint.
5. Generates Flutter Web platform files when missing.
6. Runs `flutter pub get`.
7. Launches SirisOS in Chrome using `http://localhost:8000` as its API.

The first run may download Docker images and Flutter dependencies.

If Make is unavailable, use:

```bash
bash scripts/dev-web.sh
```

### Useful commands

```bash
make backend   # Start backend services only
make status    # Show containers and API health
make logs      # Follow Docker Compose logs
make restart   # Rebuild and restart backend services
make stop      # Stop backend services
make clean     # Stop services and clean Flutter build output
```

Quitting Flutter with `q` stops the web development process but leaves the Docker backend running. Use `make stop` when finished.

## Manual development

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
