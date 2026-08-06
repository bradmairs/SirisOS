# SirisOS API

Base URL during local development: `http://localhost:8000`

## System endpoints

### `GET /`

Returns basic API metadata.

Example response:

```json
{
  "name": "SirisOS API",
  "version": "0.1.0",
  "docs": "/docs"
}
```

### `GET /health`

Returns the current API health state.

Example response:

```json
{
  "status": "ok",
  "service": "sirisos-api",
  "version": "0.1.0"
}
```

Interactive OpenAPI documentation is available at `/docs` while the service is running.
