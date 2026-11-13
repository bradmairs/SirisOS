"""The built-in exercises (6.5): standard exercise names, written for SirisOS,
each with the muscle it mostly works, the others it helps, the equipment, and
how it's logged ("weight" sets × reps, "bodyweight" reps with optional added
weight, "time" seconds, "cardio" minutes and km). Your own exercises are kept
with the rest of your gym data (store.py) and sit alongside these.
"""

from __future__ import annotations

from typing import Any

MUSCLES = ["chest", "back", "shoulders", "biceps", "triceps", "forearms", "abs", "quads", "hamstrings", "glutes", "calves", "full body", "cardio"]
EQUIPMENT = ["barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "band", "smith", "ez bar", "trap bar", "other"]

# id, name, primary, secondary, equipment, kind. 9.44: every exercise that has helpers names them; a true isolation
# (leg extension, calf raise, crunch) has none. Traps count as back, obliques as abs.
_ROWS: list[tuple[str, str, str, tuple[str, ...], str, str]] = [
    # chest
    ("bench-press", "Bench Press", "chest", ("triceps", "shoulders"), "barbell", "weight"),
    ("incline-bench-press", "Incline Bench Press", "chest", ("shoulders", "triceps"), "barbell", "weight"),
    ("decline-bench-press", "Decline Bench Press", "chest", ("triceps", "shoulders"), "barbell", "weight"),
    ("db-bench-press", "Dumbbell Bench Press", "chest", ("triceps", "shoulders"), "dumbbell", "weight"),
    ("incline-db-press", "Incline Dumbbell Press", "chest", ("shoulders", "triceps"), "dumbbell", "weight"),
    ("db-fly", "Dumbbell Fly", "chest", ("shoulders",), "dumbbell", "weight"),
    ("cable-crossover", "Cable Crossover", "chest", ("shoulders",), "cable", "weight"),
    ("pec-deck", "Pec Deck", "chest", ("shoulders",), "machine", "weight"),
    ("chest-press-machine", "Machine Chest Press", "chest", ("triceps",), "machine", "weight"),
    ("push-up", "Push-up", "chest", ("triceps", "shoulders"), "bodyweight", "bodyweight"),
    ("dip", "Dip", "chest", ("triceps", "shoulders"), "bodyweight", "bodyweight"),
    # back
    ("deadlift", "Deadlift", "back", ("hamstrings", "glutes", "forearms"), "barbell", "weight"),
    ("trap-bar-deadlift", "Trap Bar Deadlift", "quads", ("back", "glutes", "hamstrings"), "trap bar", "weight"),
    ("barbell-row", "Barbell Row", "back", ("biceps", "forearms"), "barbell", "weight"),
    ("pendlay-row", "Pendlay Row", "back", ("biceps",), "barbell", "weight"),
    ("db-row", "One-arm Dumbbell Row", "back", ("biceps",), "dumbbell", "weight"),
    ("seated-cable-row", "Seated Cable Row", "back", ("biceps",), "cable", "weight"),
    ("lat-pulldown", "Lat Pulldown", "back", ("biceps", "forearms"), "cable", "weight"),
    ("pull-up", "Pull-up", "back", ("biceps", "forearms"), "bodyweight", "bodyweight"),
    ("chin-up", "Chin-up", "back", ("biceps",), "bodyweight", "bodyweight"),
    ("t-bar-row", "T-bar Row", "back", ("biceps",), "machine", "weight"),
    ("straight-arm-pulldown", "Straight-arm Pulldown", "back", ("triceps", "shoulders"), "cable", "weight"),
    ("back-extension", "Back Extension", "back", ("glutes", "hamstrings"), "bodyweight", "bodyweight"),
    ("shrug", "Barbell Shrug", "back", ("forearms",), "barbell", "weight"),
    ("rack-pull", "Rack Pull", "back", ("glutes", "forearms"), "barbell", "weight"),
    # shoulders
    ("overhead-press", "Overhead Press", "shoulders", ("triceps",), "barbell", "weight"),
    ("db-shoulder-press", "Dumbbell Shoulder Press", "shoulders", ("triceps",), "dumbbell", "weight"),
    ("arnold-press", "Arnold Press", "shoulders", ("triceps",), "dumbbell", "weight"),
    ("lateral-raise", "Lateral Raise", "shoulders", ("back",), "dumbbell", "weight"),
    ("cable-lateral-raise", "Cable Lateral Raise", "shoulders", ("back",), "cable", "weight"),
    ("front-raise", "Front Raise", "shoulders", ("chest",), "dumbbell", "weight"),
    ("rear-delt-fly", "Rear Delt Fly", "shoulders", ("back",), "dumbbell", "weight"),
    ("face-pull", "Face Pull", "shoulders", ("back",), "cable", "weight"),
    ("upright-row", "Upright Row", "shoulders", ("back", "biceps"), "barbell", "weight"),
    ("shoulder-press-machine", "Machine Shoulder Press", "shoulders", ("triceps",), "machine", "weight"),
    # arms
    ("barbell-curl", "Barbell Curl", "biceps", ("forearms",), "barbell", "weight"),
    ("db-curl", "Dumbbell Curl", "biceps", ("forearms",), "dumbbell", "weight"),
    ("hammer-curl", "Hammer Curl", "biceps", ("forearms",), "dumbbell", "weight"),
    ("preacher-curl", "Preacher Curl", "biceps", ("forearms",), "ez bar", "weight"),
    ("cable-curl", "Cable Curl", "biceps", ("forearms",), "cable", "weight"),
    ("incline-db-curl", "Incline Dumbbell Curl", "biceps", ("forearms",), "dumbbell", "weight"),
    ("tricep-pushdown", "Triceps Pushdown", "triceps", (), "cable", "weight"),
    ("overhead-tricep-extension", "Overhead Triceps Extension", "triceps", ("shoulders",), "dumbbell", "weight"),
    ("skull-crusher", "Lying Triceps Extension", "triceps", (), "ez bar", "weight"),
    ("close-grip-bench", "Close-grip Bench Press", "triceps", ("chest", "shoulders"), "barbell", "weight"),
    ("bench-dip", "Bench Dip", "triceps", ("chest", "shoulders"), "bodyweight", "bodyweight"),
    ("wrist-curl", "Wrist Curl", "forearms", (), "barbell", "weight"),
    ("farmers-carry", "Farmer's Carry", "forearms", ("back", "full body"), "dumbbell", "time"),
    # legs
    ("back-squat", "Back Squat", "quads", ("glutes", "hamstrings"), "barbell", "weight"),
    ("front-squat", "Front Squat", "quads", ("glutes", "abs"), "barbell", "weight"),
    ("goblet-squat", "Goblet Squat", "quads", ("glutes",), "dumbbell", "weight"),
    ("leg-press", "Leg Press", "quads", ("glutes", "hamstrings"), "machine", "weight"),
    ("hack-squat", "Hack Squat", "quads", ("glutes", "hamstrings"), "machine", "weight"),
    ("leg-extension", "Leg Extension", "quads", (), "machine", "weight"),
    ("bulgarian-split-squat", "Bulgarian Split Squat", "quads", ("glutes", "hamstrings"), "dumbbell", "weight"),
    ("walking-lunge", "Walking Lunge", "quads", ("glutes", "hamstrings"), "dumbbell", "weight"),
    ("step-up", "Step-up", "quads", ("glutes", "hamstrings"), "dumbbell", "weight"),
    ("romanian-deadlift", "Romanian Deadlift", "hamstrings", ("glutes", "back"), "barbell", "weight"),
    ("db-romanian-deadlift", "Dumbbell Romanian Deadlift", "hamstrings", ("glutes", "back"), "dumbbell", "weight"),
    ("lying-leg-curl", "Lying Leg Curl", "hamstrings", ("calves",), "machine", "weight"),
    ("seated-leg-curl", "Seated Leg Curl", "hamstrings", ("calves",), "machine", "weight"),
    ("good-morning", "Good Morning", "hamstrings", ("back", "glutes"), "barbell", "weight"),
    ("hip-thrust", "Hip Thrust", "glutes", ("hamstrings",), "barbell", "weight"),
    ("glute-bridge", "Glute Bridge", "glutes", ("hamstrings",), "bodyweight", "bodyweight"),
    ("cable-kickback", "Cable Kickback", "glutes", ("hamstrings",), "cable", "weight"),
    ("hip-abduction", "Hip Abduction Machine", "glutes", (), "machine", "weight"),
    ("standing-calf-raise", "Standing Calf Raise", "calves", (), "machine", "weight"),
    ("seated-calf-raise", "Seated Calf Raise", "calves", (), "machine", "weight"),
    # core
    ("plank", "Plank", "abs", ("shoulders", "glutes"), "bodyweight", "time"),
    ("side-plank", "Side Plank", "abs", ("shoulders", "glutes"), "bodyweight", "time"),
    ("crunch", "Crunch", "abs", (), "bodyweight", "bodyweight"),
    ("hanging-leg-raise", "Hanging Leg Raise", "abs", ("forearms", "back"), "bodyweight", "bodyweight"),
    ("cable-crunch", "Cable Crunch", "abs", (), "cable", "weight"),
    ("ab-wheel", "Ab Wheel Rollout", "abs", ("shoulders",), "other", "bodyweight"),
    ("russian-twist", "Russian Twist", "abs", (), "bodyweight", "bodyweight"),
    ("pallof-press", "Pallof Press", "abs", ("shoulders",), "cable", "weight"),
    # full body
    ("kb-swing", "Kettlebell Swing", "glutes", ("hamstrings", "back"), "kettlebell", "weight"),
    ("clean", "Power Clean", "full body", ("back", "quads", "shoulders"), "barbell", "weight"),
    ("thruster", "Thruster", "full body", ("quads", "shoulders"), "barbell", "weight"),
    ("burpee", "Burpee", "full body", ("chest", "quads"), "bodyweight", "bodyweight"),
    # cardio
    ("treadmill", "Treadmill", "cardio", ("quads", "calves"), "machine", "cardio"),
    ("rowing-machine", "Rowing Machine", "cardio", ("back", "quads"), "machine", "cardio"),
    ("exercise-bike", "Exercise Bike", "cardio", ("quads", "glutes"), "machine", "cardio"),
    ("elliptical", "Elliptical", "cardio", ("quads", "glutes"), "machine", "cardio"),
    ("stair-climber", "Stair Climber", "cardio", ("glutes", "calves"), "machine", "cardio"),
    ("jump-rope", "Jump Rope", "cardio", ("calves",), "other", "time"),
    ("air-bike", "Air Bike", "cardio", ("full body",), "machine", "cardio"),
    ("ski-erg", "Ski Erg", "cardio", ("back", "triceps"), "machine", "cardio"),
    ("run", "Run", "cardio", ("quads", "calves"), "other", "cardio"),
    ("circuit", "Circuit", "cardio", ("full body",), "other", "cardio"),
    ("sled-push", "Sled Push", "cardio", ("quads", "glutes"), "other", "cardio"),
]

BUILTIN: dict[str, dict[str, Any]] = {
    r[0]: {"id": r[0], "name": r[1], "primary": r[2], "secondary": list(r[3]), "equipment": r[4], "kind": r[5], "custom": False}
    for r in _ROWS
}


# 8.8: two or three short reminders for the main lifts, shown on the workout card (yours replace them).
CUES: dict[str, str] = {
    "back-squat": "Brace before you descend · knees out over the toes · drive up through the whole foot",
    "front-squat": "Elbows high · upright chest · sit between the hips",
    "bench-press": "Shoulder blades back and down · feet planted · bar to the lower chest",
    "incline-bench-press": "Shoulder blades pinned · bar to the upper chest · elbows under the bar",
    "db-bench-press": "Shoulder blades back · elbows about 45° · press up and slightly in",
    "incline-db-press": "Shoulder blades back · elbows about 45° · don't bounce at the bottom",
    "deadlift": "Bar over mid-foot · brace and take the slack out · push the floor away",
    "romanian-deadlift": "Soft knees · hips back · bar close to the legs",
    "overhead-press": "Squeeze the glutes · bar close to the face · head through at the top",
    "barbell-row": "Hinge to about 45° · pull to the lower ribs · no jerking",
    "pull-up": "Full hang to start · chest to the bar · control the way down",
    "lat-pulldown": "Lean back slightly · elbows down to the ribs · don't swing",
    "seated-cable-row": "Tall chest · pull to the waist · shoulders down, not up",
    "leg-press": "Feet shoulder-width · don't let the lower back lift · don't lock the knees",
    "lateral-raise": "Lead with the elbows · stop at shoulder height · slow on the way down",
    "hip-thrust": "Chin tucked · drive through the heels · squeeze at the top",
}
