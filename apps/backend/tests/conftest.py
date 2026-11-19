import pytest
import os
import tempfile

# Engineering stores default to /app/data; keep any test that forgets to
# point them elsewhere out of the real data directory.
os.environ.setdefault("SIRISOS_PROJECTS_PATH", f"{tempfile.mkdtemp()}/projects.json")
os.environ.setdefault("SIRISOS_DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("SIRISOS_ALLOW_DEV_SECRETS", "1")  # 9.5: the fixed development secret and password, for tests only
os.environ.setdefault("SIRISOS_PUSH_ENABLED", "0")
os.environ.setdefault("SIRISOS_STATUS_SAMPLER", "0")
os.environ.setdefault("SIRISOS_BACKUPS", "0")
os.environ.setdefault("SIRISOS_MACHINE_WATCH", "0")  # 8.9: not this computer's disk in the tests
os.environ.setdefault("SIRISOS_WATCH", "0")
os.environ.setdefault("SIRISOS_SELFTEST", "0")
os.environ.setdefault("SIRISOS_BUILT_IN_LINKS", "0")


def pytest_configure(config):
    config.addinivalue_line("markers", "weekend: runs with the real weekend rule for work tasks (9.51)")


@pytest.fixture(autouse=True)
def _weekdays_only(monkeypatch, request):
    """9.51: work tasks hide at the weekend. Tests written for any day run as on a weekday, so they don't change with
    the calendar; tests of the weekend itself are marked `weekend` and keep the real rule."""
    if request.node.get_closest_marker("weekend"):
        return
    from app.tasks import service as tasks_service

    monkeypatch.setattr(tasks_service, "weekend", lambda on: False)


@pytest.fixture(autouse=True)
def _own_digest(monkeypatch, tmp_path):
    """10.2: each test starts with an empty notification roundup."""
    monkeypatch.setenv("SIRISOS_DIGEST_PATH", str(tmp_path / "push-digest.json"))
