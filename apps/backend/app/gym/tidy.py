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

A merge can be undone (8.6): each one keeps the exercise that went and how the
workouts it touched looked, and undoing puts them back and remembers the pair
as not the same. You can also say a suggested pair isn't the same, and it
isn't suggested again.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
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
    apart = {frozenset(p) for p in doc.not_duplicates}
    out = []
    for mine in doc.exercises:
        me = names[mine.id]
        better = [e for e in names.values() if e["id"] != mine.id and frozenset((mine.id, e["id"])) not in apart and e.get("kind", "weight") == mine.kind and rank(e) > rank(me) and _same(mine.name, e["name"])]
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
    record = store.MergeRecord(at=datetime.now(timezone.utc).isoformat(timespec="seconds"), source=next(e for e in doc.exercises if e.id == source),
                               into=into, into_name=service.exercises(doc)[into]["name"])
    moved = workouts = 0
    for s in doc.sessions:
        if any(e.exercise == source for e in s.entries):
            record.before[s.id] = [(i, e.model_copy(deep=True)) for i, e in enumerate(s.entries) if e.exercise in (source, into)]
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
        for di, d in enumerate(r.days):
            for pi, p in enumerate(d.exercises):
                if p.exercise == source:
                    p.exercise = into
                    record.routines.append((r.id or "", di, pi))
    doc.exercises = [e for e in doc.exercises if e.id != source]
    record.sets_moved = moved
    doc.merges = [*doc.merges, record][-200:]
    return {"sets_moved": moved, "workouts": workouts, "into": into, "merge": record.id}


def merges(doc: store.GymDoc) -> list[dict[str, Any]]:
    """The merges you can undo, newest first."""
    return [{"id": m.id, "at": m.at, "from_name": m.source.name, "into": m.into, "into_name": m.into_name, "sets_moved": m.sets_moved, "workouts": len(m.before)}
            for m in reversed(doc.merges)]


def unmerge(doc: store.GymDoc, merge_id: str) -> dict[str, Any]:
    """Put a merge back: the exercise returns, the workouts it touched get their entries for the two back as they were,
    routines point at it again, and the pair isn't suggested again. Raises ValueError for one that isn't there."""
    m = next((x for x in doc.merges if x.id == merge_id), None)
    if m is None:
        raise ValueError("That merge isn't there to undo.")
    source = m.source.id
    if not any(e.id == source for e in doc.exercises):
        doc.exercises.append(m.source)
    sessions = {s.id: s for s in doc.sessions}
    restored = 0
    for sid, was in m.before.items():
        s = sessions.get(sid)
        if s is None:  # deleted since
            continue
        entries = [e for e in s.entries if e.exercise != m.into]
        for i, e in sorted(was, key=lambda x: x[0]):
            entries.insert(min(i, len(entries)), e)
            restored += len(e.sets) if e.exercise == source else 0
        s.entries = entries
    routines = {r.id: r for r in doc.routines}
    for rid, di, pi in m.routines:
        r = routines.get(rid)
        try:
            p = r.days[di].exercises[pi] if r else None
        except IndexError:
            p = None
        if p is not None and p.exercise == m.into:
            p.exercise = source
    doc.merges = [x for x in doc.merges if x.id != merge_id]
    not_same(doc, source, m.into)
    return {"exercise": source, "name": m.source.name, "sets_back": restored, "workouts": len(m.before)}


def not_same(doc: store.GymDoc, a: str, b: str) -> None:
    """Remember that two exercises aren't the same, so they aren't suggested as a pair again."""
    if a != b and not any(set(p) == {a, b} for p in doc.not_duplicates):
        doc.not_duplicates = [*doc.not_duplicates, [a, b]][-500:]
