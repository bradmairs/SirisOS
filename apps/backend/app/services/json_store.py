"""Small JSON documents kept in the data directory, written atomically
(a temp file renamed over the old one), so a crash never leaves half a file."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def data_path(env: str, filename: str) -> Path:
    """`env` overrides one file's location; SIRISOS_DATA_DIR moves them all
    (the default is /app/data, the container's data volume)."""
    return Path(os.getenv(env) or Path(os.getenv("SIRISOS_DATA_DIR", "/app/data")) / filename)


def read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.stem}-", suffix=".tmp", delete=False) as handle:
            handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            temp = Path(handle.name)
        temp.replace(path)
