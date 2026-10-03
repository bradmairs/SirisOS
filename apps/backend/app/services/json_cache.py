"""Parsed-JSON cache keyed by file identity (path, mtime, size).

The standards library is read on every search and SirisHydro question:
every document's metadata plus its full page-text index, which can be
megabytes of JSON. Re-parsing all of it per keystroke is the slowest thing
the API does. Files only change on upload, revision, archive and restore,
and each of those rewrites the file (new mtime/size), so a cached parse is
reused until then.

Cached values are shared between callers: treat them as read-only, and copy
before mutating (e.g. `dict(value)`).
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

MAX_ENTRIES = 256

_lock = threading.Lock()
_cache: "OrderedDict[str, tuple[int, int, Any]]" = OrderedDict()


def load_json(path: Path) -> Any:
    """Like json.loads(path.read_text()), raising the same OSError or
    json.JSONDecodeError, but parsed at most once per file version."""
    stat = path.stat()
    key = str(path)
    with _lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] == stat.st_mtime_ns and hit[1] == stat.st_size:
            _cache.move_to_end(key)
            return hit[2]
    value = json.loads(path.read_text(encoding="utf-8"))
    with _lock:
        _cache[key] = (stat.st_mtime_ns, stat.st_size, value)
        _cache.move_to_end(key)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)
    return value


def clear() -> None:
    with _lock:
        _cache.clear()
