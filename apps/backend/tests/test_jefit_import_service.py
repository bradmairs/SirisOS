from app.services.gym_service import GymService
from app.services.jefit_import_service import JefitImportService, JefitParsedSet, _parse_logs, parse_jefit_export

# A minimal but structurally faithful slice of a real JEFIT "Backup & Export"
# CSV -- section markers, blank-line/divider separators and column shapes
# all match the real format, with synthetic data (not a real user's export).
_SAMPLE_EXPORT = """
### SETTING ##########################################

row_id,USERID,TIMESTAMP,gender
1,1,"2026-01-01 00:00:00",M


######################################################

### EXERCISE LOGS ####################################

USERID,TIMESTAMP,belongSys,logs,_id,record,mydate,eid,ename,day_item_id,belongsession,logTime,interval_logs,auto_generated
1,"2026-01-01 00:00:00",1,"60x10,65x8,65x8",1,86.67,2026-01-01,21,"Barbell Bench Press",1,1000,1,,
1,"2026-01-01 00:00:00",1,"20x10,20x10,20x10",2,26.67,2026-01-01,90,"Dumbbell Row",2,1000,1,,
1,"2026-01-05 00:00:00",1,"100x5,100x5",3,116.67,2026-01-05,127,"Barbell Squat",3,2000,2,,


######################################################

### EXERCISE SET LOGS ################################

_id,userid,exercise_log_id,set_index,weight_lbs,reps
1,1,1,0,132.28,10
"""

_EMPTY_EXPORT = """
### SETTING ##########################################

row_id,USERID
1,1
"""


def test_parse_groups_exercises_by_session() -> None:
    sessions = parse_jefit_export(_SAMPLE_EXPORT)

    assert len(sessions) == 2
    first, second = sessions
    assert first.external_id == "1000"
    assert len(first.exercises) == 2
    assert first.exercises[0].name == "Barbell Bench Press"
    assert first.exercises[0].sets == [
        JefitParsedSet(60.0, 10),
        JefitParsedSet(65.0, 8),
        JefitParsedSet(65.0, 8),
    ]
    assert second.external_id == "2000"
    assert second.workout_date.isoformat() == "2026-01-05"


def test_parse_returns_nothing_when_no_exercise_logs_section_exists() -> None:
    assert parse_jefit_export(_EMPTY_EXPORT) == []


def test_parse_logs_rounds_fractional_reps_and_drops_zero_weight() -> None:
    sets = _parse_logs("18.00003x8,0x10,45.25x6")
    assert sets == [
        JefitParsedSet(18.0, 8),
        JefitParsedSet(45.2, 6),
    ]


def test_parse_logs_skips_malformed_entries_without_raising() -> None:
    assert _parse_logs("not-a-set,60x10") == [JefitParsedSet(60.0, 10)]


def _service(tmp_path, monkeypatch) -> GymService:
    # An isolated SQLite DB per test, not the conftest-shared one other gym
    # tests use -- these tests assert exact workout counts, which the shared
    # DB (relied on elsewhere via unique exercise names, not isolation)
    # would make flaky depending on test order. monkeypatch reverts this
    # after the test, unlike a raw os.environ mutation which would leak into
    # whichever gym test runs next in the same process.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/jefit-import-test.db")
    service = GymService()
    service.initialise()
    return service


def test_import_creates_a_workout_per_session(tmp_path, monkeypatch) -> None:
    gym = _service(tmp_path, monkeypatch)
    result = JefitImportService(gym_service=gym).import_export(_SAMPLE_EXPORT)

    assert result.sessions_imported == 2
    assert result.sessions_skipped == 0
    assert result.sets_imported == 8
    assert result.earliest_date.isoformat() == "2026-01-01"
    assert result.latest_date.isoformat() == "2026-01-05"
    assert result.errors == []

    workouts = gym.list_workouts()
    assert len(workouts) == 2
    assert all(item.source == "jefit" for item in workouts)
    assert {item.external_id for item in workouts} == {"1000", "2000"}


def test_reimporting_the_same_export_is_idempotent(tmp_path, monkeypatch) -> None:
    gym = _service(tmp_path, monkeypatch)
    importer = JefitImportService(gym_service=gym)
    importer.import_export(_SAMPLE_EXPORT)

    second = importer.import_export(_SAMPLE_EXPORT)

    assert second.sessions_imported == 0
    assert second.sessions_skipped == 2
    assert len(gym.list_workouts()) == 2


def test_a_later_export_only_imports_genuinely_new_sessions(tmp_path, monkeypatch) -> None:
    gym = _service(tmp_path, monkeypatch)
    importer = JefitImportService(gym_service=gym)
    importer.import_export(_SAMPLE_EXPORT)

    extended_export = _SAMPLE_EXPORT.replace(
        '1,"2026-01-05 00:00:00",1,"100x5,100x5",3,116.67,2026-01-05,127,"Barbell Squat",3,2000,2,,',
        '1,"2026-01-05 00:00:00",1,"100x5,100x5",3,116.67,2026-01-05,127,"Barbell Squat",3,2000,2,,\n'
        '1,"2026-01-10 00:00:00",1,"110x5,110x5",4,128.33,2026-01-10,127,"Barbell Squat",4,3000,2,,',
    )
    result = importer.import_export(extended_export)

    assert result.sessions_imported == 1
    assert result.sessions_skipped == 2
    assert len(gym.list_workouts()) == 3


def test_imported_sets_feed_the_same_analytics_as_manual_logging(tmp_path, monkeypatch) -> None:
    gym = _service(tmp_path, monkeypatch)
    JefitImportService(gym_service=gym).import_export(_SAMPLE_EXPORT)

    summary = gym.get_exercise("Barbell Bench Press")
    assert summary is not None
    assert summary.best_weight_kg == 65.0
    assert summary.set_count == 3

    suggestion = gym.suggest_progressive_overload("Barbell Bench Press")
    assert suggestion.status in {"progress", "repeat"}


def test_empty_export_reports_an_error_not_a_crash(tmp_path, monkeypatch) -> None:
    gym = _service(tmp_path, monkeypatch)
    result = JefitImportService(gym_service=gym).import_export(_EMPTY_EXPORT)

    assert result.sessions_imported == 0
    assert result.errors != []
