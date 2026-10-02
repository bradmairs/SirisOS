import os
import tempfile

# Engineering stores default to /app/data; keep any test that forgets to
# point them elsewhere out of the real data directory.
os.environ.setdefault("SIRISOS_PROJECTS_PATH", f"{tempfile.mkdtemp()}/projects.json")
