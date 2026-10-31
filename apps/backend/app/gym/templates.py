"""Starter routines (6.5), as starting points to copy and change."""

from __future__ import annotations

from app.gym.store import PlanExercise, Routine, RoutineDay


def _d(name: str, *rows: tuple[str, int, str, int]) -> RoutineDay:
    return RoutineDay(name=name, exercises=[PlanExercise(exercise=e, sets=s, reps=r, rest_s=rest) for e, s, r, rest in rows])


def templates() -> list[Routine]:
    return [
        Routine(id="tpl-full-body", name="Full body, 3 days", note="Three days a week with a rest day between.", days=[
            _d("Day A", ("back-squat", 3, "5-8", 150), ("bench-press", 3, "5-8", 150), ("barbell-row", 3, "8-10", 120), ("plank", 3, "30-60", 60)),
            _d("Day B", ("romanian-deadlift", 3, "6-10", 150), ("overhead-press", 3, "6-8", 120), ("lat-pulldown", 3, "8-12", 90), ("walking-lunge", 2, "10-12", 90)),
            _d("Day C", ("deadlift", 3, "3-5", 180), ("incline-db-press", 3, "8-12", 90), ("seated-cable-row", 3, "10-12", 90), ("hanging-leg-raise", 3, "8-15", 60)),
        ]),
        Routine(id="tpl-ppl", name="Push, pull, legs", note="Three days, or twice through in a week.", days=[
            _d("Push", ("bench-press", 4, "5-8", 150), ("db-shoulder-press", 3, "8-12", 90), ("incline-db-press", 3, "8-12", 90),
               ("lateral-raise", 3, "12-15", 60), ("tricep-pushdown", 3, "10-15", 60)),
            _d("Pull", ("deadlift", 3, "3-5", 180), ("pull-up", 3, "6-10", 120), ("barbell-row", 3, "8-10", 90), ("face-pull", 3, "12-15", 60),
               ("db-curl", 3, "10-12", 60)),
            _d("Legs", ("back-squat", 4, "5-8", 180), ("romanian-deadlift", 3, "8-10", 120), ("leg-press", 3, "10-12", 90),
               ("lying-leg-curl", 3, "10-12", 60), ("standing-calf-raise", 4, "10-15", 60)),
        ]),
        Routine(id="tpl-upper-lower", name="Upper, lower", note="Four days: upper, lower, rest, upper, lower.", days=[
            _d("Upper 1", ("bench-press", 4, "5-8", 150), ("barbell-row", 4, "6-10", 120), ("overhead-press", 3, "8-10", 90), ("lat-pulldown", 3, "10-12", 90), ("barbell-curl", 2, "10-12", 60)),
            _d("Lower 1", ("back-squat", 4, "5-8", 180), ("romanian-deadlift", 3, "8-10", 120), ("leg-extension", 3, "12-15", 60), ("standing-calf-raise", 3, "10-15", 60)),
            _d("Upper 2", ("incline-bench-press", 3, "8-10", 120), ("pull-up", 3, "6-10", 120), ("db-shoulder-press", 3, "10-12", 90), ("seated-cable-row", 3, "10-12", 90), ("tricep-pushdown", 2, "12-15", 60)),
            _d("Lower 2", ("deadlift", 3, "3-5", 180), ("bulgarian-split-squat", 3, "8-10", 90), ("lying-leg-curl", 3, "10-12", 60), ("hip-thrust", 3, "8-12", 90)),
        ]),
        Routine(id="tpl-5x5", name="Strength 5×5", note="Two alternating days, three times a week; add weight each time you make all five sets.", days=[
            _d("A", ("back-squat", 5, "5", 180), ("bench-press", 5, "5", 180), ("barbell-row", 5, "5", 180)),
            _d("B", ("back-squat", 5, "5", 180), ("overhead-press", 5, "5", 180), ("deadlift", 1, "5", 180)),
        ]),
    ]
