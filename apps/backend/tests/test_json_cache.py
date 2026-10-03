import json
import os

from app.services import json_cache


def test_parses_once_per_file_version(tmp_path, monkeypatch):
    path = tmp_path / "index.json"
    path.write_text(json.dumps([{"page": 1, "text": "a"}]), encoding="utf-8")
    json_cache.clear()
    calls = []
    real = json.loads
    monkeypatch.setattr(json_cache.json, "loads", lambda s: calls.append(1) or real(s))

    first = json_cache.load_json(path)
    assert json_cache.load_json(path) is first
    assert len(calls) == 1

    path.write_text(json.dumps([{"page": 1, "text": "b"}, {"page": 2, "text": "c"}]), encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert json_cache.load_json(path)[1]["text"] == "c"
    assert len(calls) == 2


def test_missing_file_raises_like_read_text(tmp_path):
    try:
        json_cache.load_json(tmp_path / "missing.json")
    except OSError:
        pass
    else:
        raise AssertionError("expected OSError")
