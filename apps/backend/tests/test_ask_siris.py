from datetime import date, timedelta
from pathlib import Path

from app.services.ask_siris_service import AskSirisService
from app.services.coach_service import CoachService
from app.services.gym_service import GymService
from app.services.running_service import RunningService
from app.services.training_load_service import TrainingLoadService

# AskSirisService matches exercises by substring against every logged
# exercise name and aggregates runs/workouts across date ranges, so per-test
# isolation needs a genuinely separate database rather than unique
# names/dates within a shared one. Matches the tmp_path/monkeypatch pattern
# used by the health/conflict/achievement test suites.


def _monday(year: int, week_offset: int) -> date:
    anchor = date(year, 3, 1)
    anchor -= timedelta(days=anchor.weekday())
    return anchor + timedelta(weeks=week_offset)


def _services(tmp_path: Path, monkeypatch) -> tuple[RunningService, GymService, AskSirisService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/ask_siris.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    coach = CoachService(
        running_service=running,
        gym_service=gym,
        training_load_service=TrainingLoadService(running_service=running, gym_service=gym),
    )
    ask_siris = AskSirisService(running_service=running, gym_service=gym, coach_service=coach)
    return running, gym, ask_siris


def test_unrecognised_question_returns_suggestions(tmp_path: Path, monkeypatch) -> None:
    _, _, ask_siris = _services(tmp_path, monkeypatch)

    result = ask_siris.answer("What's the weather like today?")

    assert result.understood is False
    assert result.suggestions


def test_last_time_at_weight_found(tmp_path: Path, monkeypatch) -> None:
    _, gym, ask_siris = _services(tmp_path, monkeypatch)
    exercise = "Deadlift"
    today = _monday(2026, 0)

    gym.create_workout(
        workout_date=today - timedelta(weeks=1),
        name="Pull",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 140, "reps": 3, "rir": 1}],
    )

    result = ask_siris.answer(f"When did I last {exercise} 140kg?", today=today)

    assert result.understood is True
    assert (today - timedelta(weeks=1)).isoformat() in result.answer


def test_last_time_at_weight_not_yet_reached(tmp_path: Path, monkeypatch) -> None:
    _, gym, ask_siris = _services(tmp_path, monkeypatch)
    exercise = "Squat"
    today = _monday(2026, 0)

    gym.create_workout(
        workout_date=today,
        name="Legs",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 100, "reps": 5, "rir": 2}],
    )

    result = ask_siris.answer(f"When did I last {exercise} 140kg?", today=today)

    assert result.understood is True
    assert "haven't lifted" in result.answer


def test_exercise_progress_since_date(tmp_path: Path, monkeypatch) -> None:
    _, gym, ask_siris = _services(tmp_path, monkeypatch)
    exercise = "Bench Press"
    since = _monday(2026, 4)
    today = _monday(2026, 8)

    gym.create_workout(
        workout_date=since - timedelta(weeks=1),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today,
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 90, "reps": 8, "rir": 2}],
    )

    result = ask_siris.answer(
        f"How much has my {exercise} improved since {since.isoformat()}?", today=today
    )

    assert result.understood is True
    assert "up" in result.answer


def test_most_improved_exercise(tmp_path: Path, monkeypatch) -> None:
    _, gym, ask_siris = _services(tmp_path, monkeypatch)
    improved = "Overhead Press"
    steady = "Bicep Curl"
    today = _monday(2026, 0)
    old = today - timedelta(days=120)

    gym.create_workout(
        workout_date=old, name="Push", notes=None,
        sets=[{"exercise": improved, "weight_kg": 40, "reps": 8, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[{"exercise": improved, "weight_kg": 55, "reps": 8, "rir": 2}],
    )
    gym.create_workout(
        workout_date=old, name="Push", notes=None,
        sets=[{"exercise": steady, "weight_kg": 20, "reps": 10, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[{"exercise": steady, "weight_kg": 20, "reps": 10, "rir": 2}],
    )

    result = ask_siris.answer("Which exercise has improved the most?", today=today)

    assert result.understood is True
    assert improved in result.answer


def test_best_distance(tmp_path: Path, monkeypatch) -> None:
    running, _, ask_siris = _services(tmp_path, monkeypatch)
    today = _monday(2026, 0)

    running.create_run(
        run_date=today - timedelta(weeks=1),
        run_type="outdoor",
        distance_km=5.0,
        average_pace_seconds_per_km=330,
        average_heart_rate=150,
    )
    running.create_run(
        run_date=today,
        run_type="outdoor",
        distance_km=5.1,
        average_pace_seconds_per_km=300,
        average_heart_rate=150,
    )

    result = ask_siris.answer("What's my best 5k this year?", today=today)

    assert result.understood is True
    assert today.isoformat() in result.answer


def test_training_counts_filtered_by_workout_name(tmp_path: Path, monkeypatch) -> None:
    _, gym, ask_siris = _services(tmp_path, monkeypatch)
    today = _monday(2026, 0)

    gym.create_workout(
        workout_date=today, name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today - timedelta(days=2), name="Push", notes=None,
        sets=[{"exercise": "Bench", "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    result = ask_siris.answer("How many leg workouts have I done this week?", today=today)

    assert result.understood is True
    assert "1" in result.answer


def test_weekly_summary_reuses_coach_headline(tmp_path: Path, monkeypatch) -> None:
    _, _, ask_siris = _services(tmp_path, monkeypatch)
    today = _monday(2026, 0)

    result = ask_siris.answer("How's my training going this week?", today=today)

    assert result.understood is True
    assert len(result.answer) > 0


def test_can_i_train_today_composes_conflict_and_load_guidance(tmp_path: Path, monkeypatch) -> None:
    _, _, ask_siris = _services(tmp_path, monkeypatch)
    today = _monday(2026, 0)

    result = ask_siris.answer("Can I train today?", today=today)

    assert result.understood is True
    # With no Health data ingested and no training history yet, both
    # underlying deterministic signals should say so plainly.
    assert "recovery data" in result.answer.lower()
    assert "not enough training history" in result.answer.lower()
    assert result.facts["conflict_status"] == "insufficient_data"
    assert result.facts["combined_index"] is None


def test_should_i_run_tonight_is_recognised(tmp_path: Path, monkeypatch) -> None:
    _, _, ask_siris = _services(tmp_path, monkeypatch)
    today = _monday(2026, 0)

    result = ask_siris.answer("Should I run tonight?", today=today)

    assert result.understood is True


def test_readiness_question_without_a_day_reference_is_not_recognised(
    tmp_path: Path, monkeypatch
) -> None:
    _, _, ask_siris = _services(tmp_path, monkeypatch)
    today = _monday(2026, 0)

    result = ask_siris.answer("Should I train more often?", today=today)

    assert result.understood is False


def test_should_i_run_today_flags_fatigued_legs(tmp_path: Path, monkeypatch) -> None:
    # muscle_group_fatigue() reasons from the real calendar date (no
    # reference-date override like TrainingConflictService/TrainingLoadService
    # have), so the fixture data and the `today` passed to answer() both need
    # to line up with the real date.today() rather than an arbitrary Monday.
    _, gym, ask_siris = _services(tmp_path, monkeypatch)
    today = date.today()
    for weeks_ago in (2, 3, 4):
        gym.create_workout(
            workout_date=today - timedelta(weeks=weeks_ago), name="Legs", notes=None,
            sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 4, "rir": 2}],
        )
    gym.create_workout(
        workout_date=today - timedelta(days=1), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 4, "rir": 2}],
    )
    gym.tag_exercise("Squat", "legs")

    result = ask_siris.answer("Should I run today?", today=today)

    assert result.understood is True
    assert "legs are still estimated fatigued" in result.answer
    assert result.facts["legs_fatigued"] is True


def test_should_i_run_today_stays_quiet_when_legs_are_fresh(tmp_path: Path, monkeypatch) -> None:
    _, _, ask_siris = _services(tmp_path, monkeypatch)
    today = date.today()

    result = ask_siris.answer("Should I run today?", today=today)

    assert result.understood is True
    assert "legs" not in result.answer.lower()
    assert result.facts["legs_fatigued"] is False


def test_can_i_train_today_does_not_check_leg_fatigue(tmp_path: Path, monkeypatch) -> None:
    # Leg readiness is specifically about running -- lifting doesn't imply
    # legs are the limiting factor the way running does, so the generic
    # "can I train" phrasing must not gain a leg-fatigue opinion.
    _, gym, ask_siris = _services(tmp_path, monkeypatch)
    today = date.today()
    for weeks_ago in (2, 3, 4):
        gym.create_workout(
            workout_date=today - timedelta(weeks=weeks_ago), name="Legs", notes=None,
            sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 4, "rir": 2}],
        )
    gym.create_workout(
        workout_date=today - timedelta(days=1), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 4, "rir": 2}],
    )
    gym.tag_exercise("Squat", "legs")

    result = ask_siris.answer("Can I train today?", today=today)

    assert result.understood is True
    assert "legs" not in result.answer.lower()
    assert "legs_fatigued" not in result.facts
