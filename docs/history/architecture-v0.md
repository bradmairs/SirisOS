# SirisOS Architecture

## Overview

SirisOS uses a modular client-server architecture.

```text
Flutter clients
      |
FastAPI REST API
      |
PostgreSQL
      |
Integration services
```

## Components

### Flutter application

The primary user interface for mobile, desktop, and web. It communicates only with the SirisOS API rather than directly with homelab services.

### FastAPI backend

Responsibilities include authentication, data aggregation, business logic, integrations, AI orchestration, and a stable API for all clients.

### PostgreSQL

Stores SirisOS-owned data including users, preferences, dashboard configuration, workouts, tasks, cached integration data, and audit records.

### Integration layer

Future adapters will connect Docker, Home Assistant, Plex, UniFi, Ollama, health platforms, calendars, and specialised Siris tools.

## Module boundaries

Planned modules include dashboard, homelab, health, gym, engineering, media, knowledge, automation, and AI. Each module should own its API routes, schemas, services, and frontend features.

## Security principles

- Keep credentials out of source control.
- Store secrets encrypted at rest.
- Expose SirisOS through TLS when accessed outside the local network.
- Use least-privilege service accounts and API tokens.
- Add authentication and audit logging before enabling control actions.
