# Security

SirisOS is a personal app that runs on its owner's home server; this code is public, the server and its data are not.

- **Reporting a problem:** open a private advisory under the repository's Security tab ("Report a vulnerability"), not a public issue.
- **No secrets live here.** Every key, password and token is read from the server's environment (`.env`, never committed). The ones in `.env.example` and `docker-compose.yml` are placeholders, and SirisOS refuses them (see `apps/backend/app/secrets_config.py`): a missing or placeholder `SIRISOS_JWT_SECRET` is replaced by a random key kept on the server, and a missing or placeholder `SIRISOS_ADMIN_PASSWORD` never signs in.
- **Running your own copy:** set `SIRISOS_JWT_SECRET` (`openssl rand -hex 32`) and `SIRISOS_ADMIN_PASSWORD`, add a passkey, and check System status → Security.
