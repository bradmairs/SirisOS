# SirisOS

SirisOS is a self-hosted personal operating system that brings together homelab monitoring, health and gym tracking, productivity, engineering tools, media services, knowledge management, and AI assistants.

## Initial stack

- Flutter frontend
- FastAPI backend
- PostgreSQL
- Docker Compose
- Ollama integration

## Repository layout

```text
apps/           Application code
modules/        Feature modules
infrastructure/ Deployment and service configuration
docs/           Project documentation
```

## Milestone 1

- Project scaffold
- Backend health endpoint
- PostgreSQL service
- Docker development environment
- Flutter application placeholder
- Initial architecture and roadmap documentation

## Development

Copy the example environment file, then start the backend and database:

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.
