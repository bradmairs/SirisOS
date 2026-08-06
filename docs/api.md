# SirisOS API

Base URL during local development: `http://localhost:8000`

Interactive OpenAPI documentation is available at `/docs` while the service is running.

## System endpoints

### `GET /`

Returns basic API metadata.

### `GET /health`

Returns the current API health state.

## Dashboard endpoints

### `GET /api/v1/dashboard`

Returns the combined payload used by the Flutter home dashboard. The Homelab card is populated from the local Docker host; the remaining cards are placeholders until their integrations are implemented.

## Homelab endpoints

### `GET /api/v1/homelab/docker`

Returns a read-only snapshot of the Docker host, including:

- Docker availability
- Total, running, stopped, and unhealthy counts
- Container name
- Image
- Runtime state and status
- Docker health-check state, when configured

Example response:

```json
{
  "available": true,
  "total": 8,
  "running": 8,
  "stopped": 0,
  "unhealthy": 0,
  "containers": [
    {
      "name": "plex",
      "image": "lscr.io/linuxserver/plex:latest",
      "state": "running",
      "status": "running",
      "health": null
    }
  ],
  "error": null
}
```

## Docker socket security

The development Compose stack mounts `/var/run/docker.sock` into the API container as read-only. The Docker socket is still a highly privileged interface, even with a read-only bind mount. Do not expose the SirisOS API publicly without authentication, network controls, and a more restricted Docker access strategy such as a socket proxy.
