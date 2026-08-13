from pathlib import Path

from app.services.health_ingest_service import HealthIngestService


def _service(tmp_path: Path) -> HealthIngestService:
    service = HealthIngestService(database_url=f"sqlite:///{tmp_path}/health.db")
    service.initialise()
    return service


def _payload(*metrics: tuple[str, str, list[tuple[str, float]]]) -> dict:
    return {
        "data": {
            "metrics": [
                {
                    "name": name,
                    "units": unit,
                    "data": [{"date": f"{date} 06:00:00 +0000", "qty": qty} for date, qty in entries],
                }
                for name, unit, entries in metrics
            ]
        }
    }


def test_no_data_returns_empty_summary(tmp_path: Path) -> None:
    service = _service(tmp_path)

    assert service.summary() == []


def test_single_sample_has_no_baseline(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(_payload(("heart_rate_variability", "ms", [("2026-08-10", 51.2)])))

    summary = service.summary()

    assert len(summary) == 1
    item = summary[0]
    assert item.metric_type == "heart_rate_variability"
    assert item.latest_value == 51.2
    assert item.baseline_average is None
    assert item.baseline_ratio is None
    assert item.baseline_sample_count == 0


def test_baseline_computed_from_prior_days_only(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(
        _payload(
            (
                "resting_heart_rate",
                "bpm",
                [
                    ("2026-08-05", 60.0),
                    ("2026-08-06", 60.0),
                    ("2026-08-07", 60.0),
                    ("2026-08-10", 66.0),
                ],
            )
        )
    )

    summary = service.summary()

    assert len(summary) == 1
    item = summary[0]
    assert item.latest_value == 66.0
    assert item.baseline_sample_count == 3
    assert item.baseline_average == 60.0
    assert item.baseline_ratio == 110.0


def test_baseline_excludes_same_day_as_latest(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(
        _payload(
            (
                "heart_rate_variability",
                "ms",
                [
                    ("2026-08-05", 50.0),
                    ("2026-08-06", 50.0),
                    ("2026-08-07", 50.0),
                ],
            )
        )
    )
    # A second, later reading logged on the SAME day as the "latest" reading
    # must not sneak into its own baseline.
    service.ingest(
        {
            "data": {
                "metrics": [
                    {
                        "name": "heart_rate_variability",
                        "units": "ms",
                        "data": [
                            {"date": "2026-08-10 06:00:00 +0000", "qty": 40.0},
                            {"date": "2026-08-10 22:00:00 +0000", "qty": 45.0},
                        ],
                    }
                ]
            }
        }
    )

    summary = service.summary()

    item = summary[0]
    assert item.latest_value == 45.0
    assert item.baseline_sample_count == 3
    assert item.baseline_average == 50.0


def test_multiple_metric_types_sorted(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(
        _payload(
            ("step_count", "count", [("2026-08-10", 6000.0)]),
            ("heart_rate_variability", "ms", [("2026-08-10", 51.2)]),
        )
    )

    summary = service.summary()

    assert [item.metric_type for item in summary] == ["heart_rate_variability", "step_count"]
