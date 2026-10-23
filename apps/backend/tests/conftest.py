import os
import tempfile

# Engineering stores default to /app/data; keep any test that forgets to
# point them elsewhere out of the real data directory.
os.environ.setdefault("SIRISOS_PROJECTS_PATH", f"{tempfile.mkdtemp()}/projects.json")
os.environ.setdefault("SIRISOS_DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("SIRISOS_PUSH_ENABLED", "0")
os.environ.setdefault("SIRISOS_STATUS_SAMPLER", "0")
os.environ.setdefault("SIRISOS_BACKUPS", "0")
os.environ.setdefault("SIRISOS_BUILT_IN_LINKS", "0")
