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


_EQUIPMENT_WORD = {"barbell": "barbell", "dumbbell": "dumbbell", "machine": "machine", "cable": "cable", "smith": "smith",
                   "ez bar": "ez", "trap bar": "trap", "kettlebell": "kettlebell"}


def _same(a: str, b: str, kit_a: str = "other", kit_b: str = "other") -> bool:
    """`kit_a`/`kit_b`: each exercise's equipment (8.7). "Bench Press" is a barbell lift even though its name doesn't say
    so, so "Machine Bench Press" isn't it, nor is "Dumbbell Incline Bench Press" "Incline Bench Press"."""
    if _tight(a) == _tight(b):
        return True
    x = _kit(a) | ({_EQUIPMENT_WORD[kit_a]} if kit_a in _EQUIPMENT_WORD else set())
    y = _kit(b) | ({_EQUIPMENT_WORD[kit_b]} if kit_b in _EQUIPMENT_WORD else set())
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
        better = [e for e in names.values() if e["id"] != mine.id and frozenset((mine.id, e["id"])) not in apart and e.get("kind", "weight") == mine.kind and rank(e) > rank(me) and _same(mine.name, e["name"], mine.equipment, e.get("equipment") or "other")]
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


# -- 8.7: a routine's exercises linked to the history you already have ----------------------------------------------

_STOP = {"the", "with", "on", "a", "of", "and", "grip", "wide", "close", "narrow", "single", "arm", "one"}
_SAME_JOB = [  # words that name the same movement
    {"squat", "squats"}, {"pulldown", "pull"}, {"press", "presses"}, {"curl", "curls"}, {"row", "rows"}, {"raise", "raises"},
    {"extension", "extensions", "pushdown", "pushdowns"}, {"fly", "flye", "flyes", "flys"},
]


def _job_words(name: str) -> set[str]:
    words = {w for w in _words(name) if w not in _STOP and w not in importer.EQUIP_WORDS and w != "dumbbell"}
    for group in _SAME_JOB:
        if words & group:
            words |= group
    return words


def _sessions_by_exercise(doc: store.GymDoc) -> Counter:
    return Counter(e.exercise for s in store.counted(doc) for e in s.entries if any(x.done for x in e.sets))


def history_links(doc: store.GymDoc, min_sessions: int = 5) -> list[dict[str, Any]]:
    """The active routine's exercises with little history of their own, each with up to three of your exercises,
    with real history, that look like the same thing: same main muscle and kind, sharing the words that name the
    movement. Picking one points the routine at it, so last time, what to lift and records come from your history."""
    names = service.exercises(doc)
    counts = _sessions_by_exercise(doc)
    kept = set(doc.settings.links_kept)
    out, seen = [], set()
    for r in doc.routines:
        if not r.active:
            continue
        for d in r.days:
            for p in d.exercises:
                ex = names.get(p.exercise)
                if not ex or p.exercise in seen or p.exercise in kept or counts[p.exercise] >= min_sessions:
                    continue
                seen.add(p.exercise)
                mine = _job_words(ex["name"])
                options = []
                for k, v in names.items():
                    if k == p.exercise or counts[k] < min_sessions or v.get("primary") != ex.get("primary") or v.get("kind", "weight") != ex.get("kind", "weight"):
                        continue
                    shared = mine & _job_words(v["name"])
                    if not shared:
                        continue
                    score = len(shared) / max(1, len(mine)) + (0.5 if v.get("equipment") == ex.get("equipment") else 0) + min(counts[k], 200) / 400
                    options.append((score, {"id": k, "name": v["name"], "sessions": counts[k], "equipment": v.get("equipment")}))
                if options:
                    out.append({"exercise": p.exercise, "name": ex["name"], "sessions": counts[p.exercise],
                                "options": [o for _, o in sorted(options, key=lambda t: -t[0])[:3]]})
    return out


def link(doc: store.GymDoc, source: str, into: str) -> int:
    """Every routine pointing at `source` points at `into` instead. Workouts aren't touched. Returns how many places changed."""
    if into not in service.exercises(doc):
        raise ValueError("No such exercise.")
    changed = 0
    for r in doc.routines:
        for d in r.days:
            for p in d.exercises:
                if p.exercise == source:
                    p.exercise = into
                    changed += 1
    return changed


# -- 8.7: tidying the exercises an import made ------------------------------------------------------------------------

_TIMED = re.compile(r"\b(plank|hold|wall sit|dead hang|l-sit|hollow)\b", re.I)
_BODYWEIGHT = re.compile(r"\b(sit-?ups?|crunch(es)?|push-?ups?|pull-?ups?|chin-?ups?|dips?|leg raises?|knee raises?|heel touch(es)?|"
                         r"hyperextensions?|back extensions?|burpees?|mountain climbers?|flutter kicks?|v-?ups?|bicycle)\b", re.I)
_EQUIP_GUESS = [("smith", "smith"), ("barbell", "barbell"), ("dumbbell", "dumbbell"), ("kettlebell", "kettlebell"), ("cable", "cable"),
                ("machine", "machine"), ("leverage", "machine"), ("lever", "machine"), ("ez bar", "ez bar"), ("ez-bar", "ez bar"),
                ("trap bar", "trap bar"), ("band", "band")]
_MUSCLE_GUESS = [  # whole words only, most specific first ("machine" contains "chin")
    (r"\b(calf|calves)\b", "calves"), (r"\b(hyperextensions?|back extensions?|good mornings?)\b", "back"),
    (r"\b(leg curls?|hamstrings?|romanian|stiff)\b", "hamstrings"), (r"\b(hip thrusts?|glutes?|kickbacks?)\b", "glutes"),
    (r"\b(leg extensions?|leg press|squats?|lunges?|hack squats?)\b", "quads"),
    (r"\b(external rotations?|rotator|upright rows?|up right rows?|shrugs?|face pulls?|rear delts?|reverse fly|reverse flyes|lateral raises?|deltoids?|shoulder press|military|overhead press|arnold)\b", "shoulders"),
    (r"\b(triceps?|pushdowns?|skull ?crushers?|dips?|close grip bench)\b", "triceps"), (r"\b(curls?)\b", "biceps"),
    (r"\b(wrist|forearms?|farmers?)\b", "forearms"),
    (r"\b(crunch(es)?|sit-?ups?|planks?|abs?|obliques?|russian twists?|heel touch(es)?|leg raises?|knee raises?|wood ?chops?|v-?ups?)\b", "abs"),
    (r"\b(straight arm|pulldowns?|pull downs?|pull-?ups?|chin-?ups?|rows?|pullovers?|lats?)\b", "back"),
    (r"\b(bench|chest|fly|flye|flyes|pec|push-?ups?|crossovers?)\b", "chest"),
]


def exercise_fixes(doc: store.GymDoc) -> list[dict[str, Any]]:
    """Your own exercises whose kind, equipment or main muscle looks wrong from the name, with what it should be.
    Weighted versions ("Weighted Pull-Up") stay weighted; a guess is only offered where the name is clear."""
    counts = _sessions_by_exercise(doc)
    kept = set(doc.settings.fixes_kept)
    out = []
    for e in doc.exercises:
        if e.id in kept:
            continue
        n = e.name.lower()
        change: dict[str, str] = {}
        loaded = e.equipment in ("machine", "cable", "barbell", "dumbbell", "smith", "kettlebell", "ez bar") or re.search(r"\b(machine|cable|weighted|plate|dumbbell|barbell)\b", n)
        if e.kind == "weight" and not loaded:
            if _TIMED.search(n):
                change["kind"] = "time"
            elif _BODYWEIGHT.search(n):
                change["kind"] = "bodyweight"
        if e.equipment in ("other", ""):
            found = next((v for word, v in _EQUIP_GUESS if word in n), None)
            if found:
                change["equipment"] = found
            elif change.get("kind") in ("bodyweight", "time"):
                change["equipment"] = "bodyweight"
        # 9.44: the same reading of the movement as the helper muscles (anatomy.py), so the two never disagree.
        from app.gym import anatomy

        said = anatomy.muscles_for(e.name)
        muscle = said[0] if said and said[0] not in ("full body",) else next((m for pat, m in _MUSCLE_GUESS if re.search(pat, n)), None)
        if muscle == "cardio" and e.kind != "cardio":
            muscle = None  # a walking lunge logged as weight isn't cardio
        if muscle and muscle != e.primary:
            change["primary"] = muscle
        if change:
            out.append({"id": e.id, "name": e.name, "sessions": counts[e.id], "now": {"kind": e.kind, "equipment": e.equipment, "primary": e.primary},
                        "change": change})
    return sorted(out, key=lambda x: -x["sessions"])
