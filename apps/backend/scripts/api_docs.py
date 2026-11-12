"""Write every API route into docs/api.md (8.9), from the app itself, so the list can't drift.

    python -m scripts.api_docs          # rewrite the generated section
    python -m scripts.api_docs --check  # exit 1 if it's out of date (the tests run this)

Only the part between the markers is generated; the rest of the file is written by hand.
"""

from __future__ import annotations

import inspect
import sys
from collections import defaultdict
from pathlib import Path

START, END = "<!-- routes:start -->", "<!-- routes:end -->"
DOC = Path(__file__).resolve().parents[3] / "docs" / "api.md"


def _area(path: str) -> str:
    parts = path.split("/")
    return "/".join(parts[:4]) if path.startswith("/api/v1/") else "Other"


def section() -> str:
    from fastapi.routing import APIRoute

    from app.entrypoint import app

    areas: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.include_in_schema:
            continue
        doc = (inspect.getdoc(r.endpoint) or "").split("\n\n")[0].replace("\n", " ").replace("|", "\\|").strip()
        for method in sorted(r.methods - {"HEAD", "OPTIONS"}):
            areas[_area(r.path)].append((r.path, method, doc))
    out = [START, "", "Every route, generated from the app by `apps/backend/scripts/api_docs.py` (don't edit by hand).", ""]
    for area in sorted(areas):
        out += [f"### `{area}`", "", "| Route | What it does |", "| --- | --- |"]
        for path, method, doc in sorted(areas[area]):
            out.append(f"| `{method} {path}` | {doc} |")
        out.append("")
    out.append(END)
    return "\n".join(out)


def render(current: str) -> str:
    if START in current and END in current:
        head, rest = current.split(START, 1)
        return head + section() + rest.split(END, 1)[1]
    return current.rstrip() + "\n\n## Every route\n\n" + section() + "\n"


def main(argv: list[str]) -> int:
    current = DOC.read_text()
    wanted = render(current)
    if "--check" in argv:
        if wanted != current:
            print("docs/api.md is out of date: run `python -m scripts.api_docs` in apps/backend.")
            return 1
        return 0
    DOC.write_text(wanted)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
