"""What an exercise works, from its name (9.44): the main muscle and the ones that help. Your own exercises (most from
the JEFIT import) only ever got a main muscle, guessed from the name, and no helpers, so sets per muscle, muscle
balance and recovery missed most of what a compound lift does: a row didn't count for the biceps, a squat not for the
glutes. This reads the movement from the name, most specific first, the way the built-in exercises are set.

Muscles are SirisGym's list (library.MUSCLES): traps count as back, obliques as abs.
"""

from __future__ import annotations

import re
from typing import Any

# (words in the name, main muscle, helpers), most specific first.
MOVEMENTS: list[tuple[str, str, tuple[str, ...]]] = [
    # cardio first: "rowing machine" isn't a row, "bike" isn't anything else
    (r"row(ing)? machine|rower|concept ?2|erg row", "cardio", ("back", "quads")),
    (r"ski ?erg", "cardio", ("back", "triceps")),
    (r"treadmill|running|\brun\b|jog", "cardio", ("quads", "calves")),
    (r"bike|cycl|spin", "cardio", ("quads", "glutes")),
    (r"elliptical|cross ?trainer", "cardio", ("quads", "glutes")),
    (r"stair|step ?mill", "cardio", ("glutes", "calves")),
    (r"jump ?rope|skipping", "cardio", ("calves",)),
    (r"sled", "cardio", ("quads", "glutes")),
    (r"circuit|hiit|crossfit|wod\b", "cardio", ("full body",)),
    (r"walk(ing)?\b(?! lunge)", "cardio", ("calves",)),
    # full body
    (r"(power |hang |squat )?clean|snatch", "full body", ("back", "quads", "shoulders")),
    (r"thrusters?", "full body", ("quads", "shoulders")),
    (r"burpees?", "full body", ("chest", "quads")),
    (r"(kettlebell |kb )?swings?", "glutes", ("hamstrings", "back")),
    (r"farmer|suitcase carry|carry", "forearms", ("back", "full body")),
    # legs
    (r"trap ?bar dead|hex ?bar dead", "quads", ("back", "glutes", "hamstrings")),
    (r"romanian|\brdl\b|stiff[ -]?leg", "hamstrings", ("glutes", "back")),
    (r"good ?mornings?", "hamstrings", ("back", "glutes")),
    (r"nordic|glute[ -]ham", "hamstrings", ("glutes", "calves")),
    (r"leg curls?|hamstring curls?", "hamstrings", ("calves",)),
    (r"deadlifts?|rack pulls?", "back", ("hamstrings", "glutes", "forearms")),
    (r"hip thrusts?|glute bridges?|\bbridges?\b", "glutes", ("hamstrings",)),
    (r"abduct", "glutes", ()),
    (r"adduct", "quads", ()),
    (r"front squats?", "quads", ("glutes", "abs")),
    (r"leg extensions?", "quads", ()),
    (r"split squats?|lunges?|step[ -]?ups?|pistol", "quads", ("glutes", "hamstrings")),
    (r"squats?|leg press|hack", "quads", ("glutes", "hamstrings")),
    (r"calf|calves", "calves", ()),
    (r"glute kickbacks?|cable kickbacks?|donkey kick", "glutes", ("hamstrings",)),
    # arms (before chest and back, so a "triceps dip" or "bench dip" is arms)
    (r"close[ -]?grip (bench|press)|jm press", "triceps", ("chest", "shoulders")),
    (r"(tricep|triceps|bench) dips?", "triceps", ("chest", "shoulders")),
    (r"overhead (tricep|triceps)|french press|tricep(s)? overhead", "triceps", ("shoulders",)),
    (r"tricep(s)? press|dip machine|assisted dips?", "triceps", ("chest", "shoulders")),
    (r"triceps?|skull ?crushers?|push[ -]?downs?|kickbacks?", "triceps", ()),
    (r"wrist|forearm|gripper|grip trainer|hand grip|dead ?hang", "forearms", ()),
    (r"hammer curls?|reverse curls?|cross[ -]?body curls?|zottman", "biceps", ("forearms",)),
    (r"curls?|biceps?", "biceps", ("forearms",)),
    # shoulders (before chest: a "rear delt fly" isn't a chest fly)
    (r"rear delt|reverse fly|reverse pec|face[ -]?pulls?", "shoulders", ("back",)),
    (r"lateral raises?|side raises?|lateral", "shoulders", ("back",)),
    (r"front raises?", "shoulders", ("chest",)),
    (r"upright rows?", "shoulders", ("back", "biceps")),
    (r"shrugs?", "back", ("forearms",)),
    (r"overhead press|shoulder press|military|arnold|push press|landmine press|\bohp\b", "shoulders", ("triceps",)),
    # chest
    (r"dips?", "chest", ("triceps", "shoulders")),
    (r"incline.*(press|bench)", "chest", ("shoulders", "triceps")),
    (r"bench|chest press|floor press|push[ -]?ups?|press[ -]?ups?", "chest", ("triceps", "shoulders")),
    (r"fly|flyes|flies|pec deck|crossovers?|squeeze press", "chest", ("shoulders",)),
    # back
    (r"pull[ -]?overs?", "back", ("chest", "triceps")),
    (r"straight[ -]?arm", "back", ("triceps", "shoulders")),
    (r"pull[ -]?downs?|pull[ -]?ups?|chin[ -]?ups?|\blats?\b", "back", ("biceps", "forearms")),
    (r"rows?", "back", ("biceps", "forearms")),
    (r"back extensions?|hyper ?extensions?|superman", "back", ("glutes", "hamstrings")),
    # core
    (r"planks?", "abs", ("shoulders", "glutes")),
    (r"(hanging|captain'?s?).*(leg|knee) raises?|toes to bar", "abs", ("forearms", "back")),
    (r"ab wheel|roll[ -]?outs?", "abs", ("shoulders",)),
    (r"pallof", "abs", ("shoulders",)),
    (r"crunch|sit[ -]?ups?|russian|leg raises?|knee raises?|wood ?chop|v[ -]?ups?|\babs?\b|core|oblique|dead ?bug|hollow", "abs", ()),
]


def muscles_for(name: str) -> tuple[str, tuple[str, ...]] | None:
    """(main muscle, helpers) for an exercise name, or None when it doesn't say."""
    n = name.lower()
    for words, primary, helpers in MOVEMENTS:
        if re.search(words, n):
            return primary, helpers
    return None


def fill(doc: Any) -> list[dict[str, Any]]:
    """Your exercises with no helpers get them from their name (9.44); one still on the fallback main muscle ("full
    body", what the import guessed when a name said nothing it knew) gets its main muscle too. A main muscle you chose
    is kept, and so are helpers you set. Returns what changed."""
    changed = []
    for ex in doc.exercises:
        if ex.kind == "cardio" and ex.primary == "cardio" and ex.secondary:
            continue
        found = muscles_for(ex.name)
        if not found:
            continue
        primary, helpers = found
        before = (ex.primary, list(ex.secondary))
        if ex.primary == "full body" and primary != "full body":
            ex.primary = primary
        if not ex.secondary:
            # The helpers fit the movement; if you've given it a different main muscle, they still exclude it.
            ex.secondary = [m for m in helpers if m != ex.primary][:6]
        if (ex.primary, ex.secondary) != before:
            changed.append({"id": ex.id, "name": ex.name, "primary": ex.primary, "secondary": ex.secondary})
    return changed
