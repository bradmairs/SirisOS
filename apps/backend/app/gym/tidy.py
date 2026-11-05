"""Duplicate exercises (7.0). An import can leave "Cable V Bar Pulldown" and
"Cable V Bar Pull Down" side by side, each with half the history, so neither's
records or suggestions are right. This finds them and merges one into the
other: every set moves across, nothing is removed but the spare name.

A pair is suggested when the names are the same once punctuation, spacing and
plurals are ignored, or when they differ only in equipment words and one says
less than the other ("Lat Pulldown" and "Machine Lat Pulldown"). "Barbell Curl"
and "Dumbbell Curl" say different things, so they're never paired. Only your
own exercises can go; the one kept is the built-in, or else the one with the
most sets. Nothing merges until you say so.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.gym import importer, library, service, store

SAYS_NOTHING = {"the", "with", "on", "bar"}


def _words(name: str) -> list[str]:
    return [w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else w for w in re.findall(r"[a-z0-9]+", name.lower())]


def _tight(name: str) -> str:
    return "".join(_words(name))


def _loose(name: str) -> str:
    return "".join(w for w in _words(name) if w not in importer.EQUIP_WORDS and w not in ("dumbbell",))


def _kit(name: str) -> set[str]:
    return {w for w in _words(name) if (w in importer.EQUIP_WORDS or w == "dumbbell") and w not in SAYS_NOTHING}


def _same(a: str, b: str) -> bool:
    if _tight(a) == _tight(b):
        return True
    x, y = _kit(a), _kit(b)
    return bool(_loose(a)) and _loose(a) == _loose(b) and (x <= y or y <= x)


def duplicates(doc: store.GymDoc) -> list[dict[str, Any]]:
    """Each exercise of yours that looks like another, with the one to keep."""
    names = service.exercises(doc)
    sets = Counter(e.exercise for s in doc.sessions for e in s.entries for x in e.sets if x.done)
    rank = lambda e: (e["id"] in library.BUILTIN, sets[e["id"]], e["name"])  # noqa: E731
    out = []
    for mine in doc.exercises:
        me = names[mine.id]
        better = [e for e in names.values() if e["id"] != mine.id and e.get("kind", "weight") == mine.kind and rank(e) > rank(me) and _same(mine.name, e["name"])]
        if better:
            into = max(better, key=rank)
            out.append({"from": mine.id, "from_name": mine.name, "from_sets": sets[mine.id], "into": into["id"], "into_name": into["name"], "into_sets": sets[into["id"]],
                        "sure": _tight(mine.name) == _tight(into["name"])})
    return sorted(out, key=lambda d: (not d["sure"], d["into_name"]))


def merge(doc: store.GymDoc, source: str, into: str) -> dict[str, Any]:
    """Every set of `source` becomes `into`'s; routines follow. Raises ValueError for one that can't go."""
    if source == into:
        raise ValueError("That's the same exercise.")
    if into not in service.exercises(doc):
        raise ValueError("No such exercise to merge into.")
    if not any(e.id == source for e in doc.exercises):
        raise ValueError("Only your own exercises can be merged away.")
    moved = workouts = 0
    for s in doc.sessions:
        kept: list[store.EntryLog] = []
        touched = False
        target = next((e for e in s.entries if e.exercise == into), None)
        for e in s.entries:
            if e.exercise != source:
                kept.append(e)
                continue
            touched = True
            moved += len(e.sets)
            if target is None:
                e.exercise = into
                target = e
                kept.append(e)
            else:
                target.sets = target.sets + e.sets
                if e.note:
                    target.note = f"{target.note} {e.note}".strip()[:500]
        s.entries = kept
        workouts += touched
    for r in doc.routines:
        for d in r.days:
            for p in d.exercises:
                if p.exercise == source:
                    p.exercise = into
    doc.exercises = [e for e in doc.exercises if e.id != source]
    return {"sets_moved": moved, "workouts": workouts, "into": into}
