# SirisOS

SirisOS is a self-hosted personal operating system that brings together homelab monitoring, health and gym tracking, productivity, engineering tools, media services, knowledge management, and AI assistants.

## Stack

- Flutter frontend
- Nginx web server
- FastAPI backend
- PostgreSQL
- Docker Compose
- Restricted Docker socket proxy
- Ollama integration planned

## Current capabilities

- Responsive Flutter dashboard
- Functional Dashboard, Homelab, Gym, and Siris navigation
- Live Docker container monitoring
- FastAPI dashboard and Homelab APIs
- PostgreSQL persistence under `./data/postgres`
- Docker-served web UI on port `6464`
- Restricted Docker socket proxy

## Run SirisOS

Install Docker with Docker Compose v2 and GNU Make, then run from the repository root:

```bash
cp .env.example .env
make up
```

Open SirisOS from any device on the LAN:

```text
http://192.168.0.100:6464
```

API and interactive documentation:

```text
http://192.168.0.100:8000
http://192.168.0.100:8000/docs
```

The Flutter web app is compiled inside Docker and served by Nginx. Flutter does not need to remain running on the server.

## Configuration

The browser-facing API address is compiled into the Flutter web build using `SIRISOS_API_URL` from `.env`:

```env
SIRISOS_API_URL=http://192.168.0.100:8000
```

After changing this value, rebuild the web image:

```bash
make rebuild-web
```

## Development with hot reload

For active Flutter development, install Flutter with web support and run:

```bash
make dev
```

This starts the backend services and launches Flutter's development web server at:

```text
http://192.168.0.100:6464
```

## Useful commands

```bash
make up          # Build and start the complete SirisOS stack
make dev         # Start Flutter Web with hot reload
make backend     # Start backend services only
make rebuild-web # Rebuild only the Docker-served Flutter UI
make status      # Show containers and health checks
make logs        # Follow all service logs
make restart     # Rebuild and restart the complete stack
make stop        # Stop all services
make clean       # Stop services and clean Flutter build output
```

## Persistent data

Runtime data is stored inside the repository directory:

```text
data/
├── postgres/
├── logs/
├── backups/
└── uploads/
```

Back up the `data` directory and `.env` file to preserve the installation.

## Docker access

The API does not mount the host Docker socket directly. A dedicated socket proxy exposes only the read-only Docker endpoints required for monitoring containers. The proxy still mounts `/var/run/docker.sock` because that socket belongs to the host operating system and cannot be stored inside the repository.
