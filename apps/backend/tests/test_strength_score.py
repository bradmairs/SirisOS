from datetime import date
from pathlib import Path

from app.services.gym_service import GymService

# strength_score() aggregates across all logged exercises, not scoped by
# exercise name, so it needs a genuinely isolated database per test -- same
# reasoning as muscle_group_workload()'s tests.


def _service(tmp_path: Path, monkeypatch) -> GymService:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/strength_score.db")
    service = GymService()
    service.initialise()
    return service


def test_no_tagged_exercises_gives_no_score(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    # Deliberately left untagged.

    result = service.strength_score()

    assert result.overall_score is None
    assert result.by_exercise == []
    by_group = {item.muscle_group: item for item in result.by_muscle_group}
    assert by_group["chest"].score is None
    assert by_group["chest"].exercise_count == 0


def test_single_session_reads_as_100_percent_of_its_own_peak(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    service.tag_exercise("Bench Press", "chest")

    result = service.strength_score()

    assert result.overall_score == 1.0
    assert len(result.by_exercise) == 1
    ratio = result.by_exercise[0]
    assert ratio.exercise == "Bench Press"
    assert ratio.muscle_group == "chest"
    assert ratio.ratio == 1.0
    assert ratio.current_e1rm_kg == ratio.peak_e1rm_kg


def test_current_below_peak_gives_a_ratio_under_one(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    # Peak session first.
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 100, "reps": 5, "rir": 1}],
    )
    # A lighter, more recent session -- e.g. after a deload.
    service.create_workout(
        workout_date=date(2026, 1, 8), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 3}],
    )
    service.tag_exercise("Bench Press", "chest")

    result = service.strength_score()
    ratio = result.by_exercise[0]

    assert ratio.peak_e1rm_kg > ratio.current_e1rm_kg
    assert 0 < ratio.ratio < 1.0
    assert ratio.latest_date == date(2026, 1, 8)


def test_muscle_group_score_averages_its_own_tagged_exercises_only(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    # Chest: two exercises, one at peak (ratio 1.0), one at half peak (ratio 0.5).
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[
            {"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": "Incline Press", "weight_kg": 100, "reps": 5, "rir": 1},
        ],
    )
    service.create_workout(
        workout_date=date(2026, 1, 8), name="Push", notes=None,
        sets=[{"exercise": "Incline Press", "weight_kg": 50, "reps": 5, "rir": 3}],
    )
    service.tag_exercise("Bench Press", "chest")
    service.tag_exercise("Incline Press", "chest")
    # Legs: single exercise, untouched by the chest averaging above.
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )
    service.tag_exercise("Squat", "legs")

    result = service.strength_score()
    by_group = {item.muscle_group: item for item in result.by_muscle_group}

    assert by_group["chest"].exercise_count == 2
    incline_ratio = next(item.ratio for item in result.by_exercise if item.exercise == "Incline Press")
    bench_ratio = next(item.ratio for item in result.by_exercise if item.exercise == "Bench Press")
    assert by_group["chest"].score == round((incline_ratio + bench_ratio) / 2, 3)
    assert by_group["legs"].score == 1.0
    assert by_group["legs"].exercise_count == 1


def test_overall_score_averages_muscle_groups_not_raw_exercises(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    # Chest gets 3 exercises all at peak (score 1.0); legs gets 1 exercise
    # at exactly half its peak (score 0.5). If the overall averaged raw
    # exercises instead of groups, chest's extra exercises would dominate.
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[
            {"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": "Incline Press", "weight_kg": 60, "reps": 8, "rir": 2},
            {"exercise": "Dip", "weight_kg": 20, "reps": 10, "rir": 2},
        ],
    )
    for exercise in ("Bench Press", "Incline Press", "Dip"):
        service.tag_exercise(exercise, "chest")

    service.create_workout(
        workout_date=date(2026, 1, 1), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 1}],
    )
    service.create_workout(
        workout_date=date(2026, 1, 8), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 50, "reps": 5, "rir": 4}],
    )
    service.tag_exercise("Squat", "legs")

    result = service.strength_score()
    by_group = {item.muscle_group: item for item in result.by_muscle_group}

    assert by_group["chest"].score == 1.0
    assert by_group["legs"].score is not None and by_group["legs"].score < 1.0
    expected_overall = round((by_group["chest"].score + by_group["legs"].score) / 2, 3)
    assert result.overall_score == expected_overall


def test_untagged_exercises_are_excluded_entirely(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_workout(
        workout_date=date(2026, 1, 1), name="Push", notes=None,
        sets=[
            {"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": "Unknown Machine", "weight_kg": 20, "reps": 10, "rir": 2},
        ],
    )
    service.tag_exercise("Bench Press", "chest")
    # "Unknown Machine" deliberately left untagged.

    result = service.strength_score()

    exercises = {item.exercise for item in result.by_exercise}
    assert exercises == {"Bench Press"}
