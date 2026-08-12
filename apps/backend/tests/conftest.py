import os
import tempfile

# Modules such as app.api.health create a SQLAlchemy-backed service and call
# initialise() at import time, which otherwise defaults to the production
# Postgres DSN and fails to even resolve outside of Docker Compose. Point it at
# a throwaway SQLite file so plain `pytest` works the same as CI.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/sirisos-test.db")
