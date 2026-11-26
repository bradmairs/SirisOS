"""Renumber this branch's version onto the next one after main's (11.11).

Two sessions both shipped 11.9.0 on 26-27 Nov 2026: each bumped from the same main. Run this after `git fetch` when
main has moved on (CI's version check says so): it keeps the size of the change (fix, feature or section, from how
this branch's version differs from the one it started from), takes the next number after main's, and moves
everything that carries it: VERSION, the API and web versions, the README's version line, the release notes (file
and heading) and the roadmap line. Code comments that mention the old number are listed, not changed.

    scripts/bump-version.sh rebase          # against origin/main
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def parse(v: str) -> tuple[int, int, int]:
    s, f, x = (int(p) for p in v.strip().split("."))
    return s, f, x


def size(start: tuple[int, int, int], mine: tuple[int, int, int]) -> str:
    if mine[0] != start[0]:
        return "section"
    if mine[1] != start[1]:
        return "feature"
    return "fix"


def bump(v: tuple[int, int, int], kind: str) -> str:
    s, f, x = v
    if kind == "section":
        return f"{s + 1}.0.0"
    if kind == "feature":
        return f"{s}.{f + 1}.0"
    return f"{s}.{f}.{x + 1}"


def main(base: str = "origin/main") -> int:
    mine = (ROOT / "VERSION").read_text().strip()
    main_v = git("show", f"{base}:VERSION")
    # Where this branch started: the parent of its first own commit (following its own line, so merging main in
    # doesn't move it), not the merge base, which a merge of main moves up to main itself.
    own = git("rev-list", "--first-parent", "--reverse", f"{base}..HEAD").split()
    start = git("show", f"{own[0]}^:VERSION") if own else main_v
    if parse(mine) > parse(main_v):
        print(f"{mine} is already newer than {base}'s {main_v}: nothing to do.")
        return 0
    new = bump(parse(main_v), size(parse(start), parse(mine)))
    (ROOT / "VERSION").write_text(new + "\n")
    for path, pattern, repl in (
        ("apps/backend/app/main.py", r'^API_VERSION = ".*"', f'API_VERSION = "{new}"'),
        ("apps/web/src/version.ts", r'^export const APP_VERSION = ".*";', f'export const APP_VERSION = "{new}";'),
        ("README.md", r"^\*\*Version [0-9.]+\*\* \(\[release notes\]\(docs/releases/[0-9.]+\.md\)",
         f"**Version {new}** ([release notes](docs/releases/{new}.md)"),
    ):
        p = ROOT / path
        p.write_text(re.sub(pattern, repl, p.read_text(), count=1, flags=re.M))
    old_notes, new_notes = ROOT / f"docs/releases/{mine}.md", ROOT / f"docs/releases/{new}.md"
    if old_notes.exists() and not new_notes.exists():
        text = old_notes.read_text().replace(f"# SirisOS {mine}", f"# SirisOS {new}", 1)
        new_notes.write_text(text)
        try:  # notes of the same number on main are another change's: they stay as main has them
            old_notes.write_text(git("show", f"{base}:docs/releases/{mine}.md") + "\n")
        except subprocess.CalledProcessError:
            old_notes.unlink()
    roadmap = ROOT / "docs/roadmap.md"
    lines = roadmap.read_text().splitlines()
    mine_line = [i for i, line in enumerate(lines) if line.startswith(f"{mine}:")]
    try:
        main_has = git("show", f"{base}:docs/roadmap.md").splitlines()
    except subprocess.CalledProcessError:
        main_has = []
    for i in mine_line:
        if lines[i] not in main_has:  # ours, not main's line of the same number
            lines[i] = f"{new}:" + lines[i][len(mine) + 1:]
    roadmap.write_text("\n".join(lines) + "\n")
    found = subprocess.run(["git", "grep", "-l", f"({mine})", "--", "apps"], cwd=ROOT, capture_output=True, text=True)
    stale = found.stdout.strip()
    print(f"{mine} -> {new} (main is {main_v}; a {size(parse(start), parse(mine))} after it).")
    if stale:
        print("Code comments still say " + mine + ":\n  " + stale.replace("\n", "\n  "))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
