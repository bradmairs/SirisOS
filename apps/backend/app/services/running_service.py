from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
from typing import Literal

from sqlalchemy import Date, DateTime, Float, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

RunType = Literal["outdoor", "treadmill"]

# "Comparable pace" for the lowest-heart-rate-at-pace record: within this many
# seconds/km of the new run's pace. Loose enough to catch genuinely similar
# efforts, tight enough that a 5:00/km run is never compared against a
# 6:30/km one.
LOWEST_HEART_RATE_PACE_TOLERANCE_SECONDS_PER_KM = 15


class Base(DeclarativeBase):
    pass


class RunRecordModel(Base):
    __tablename__ = "run_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    run_type: Mapped[str] = mapped_column(String(20))
    distance_km: Mapped[float] = mapped_column(Float)
    average_pace_seconds_per_km: Mapped[int] = mapped_column(Integer)
    average_heart_rate: Mapped[int] = mapped_column(Integer)
    effort_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class RunRecord:
    id: int
    run_date: date
    run_type: RunType
    distance_km: float
    average_pace_seconds_per_km: int
    average_heart_rate: int
    effort_score: float
    fitness_score: float
    created_at: datetime


@dataclass(frozen=True)
class RunningPersonalRecord:
    record_type: Literal["longest_run", "lowest_heart_rate_at_pace"]
    value: float
    previous_value: float | None
    run_date: date
    pace_seconds_per_km: int | None = None


def calculate_effort_score(
    *,
    run_type: RunType,
    distance_km: float,
    pace_seconds_per_km: int,
    average_heart_rate: int,
) -> float:
    """Return a 0–100 personal comparative running score.

    Faster pace at a lower average heart rate scores more highly, with a modest
    distance contribution and a small outdoor adjustment. This is not a medical
    or physiological assessment.
    """
    speed_kmh = 3600 / pace_seconds_per_km
    efficiency_component = (speed_kmh / average_heart_rate) * 650
    distance_component = min(distance_km, 20.0) * 1.5
    surface_adjustment = 2.0 if run_type == "outdoor" else 0.0
    score = efficiency_component + distance_component + surface_adjustment
    return round(max(0.0, min(100.0, score)), 1)


class RunningService:
    def __init__(self) -> None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos",
        )
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def create_run(
        self,
        *,
        run_date: date,
        run_type: RunType,
        distance_km: float,
        average_pace_seconds_per_km: int,
        average_heart_rate: int,
    ) -> tuple[RunRecord, list[RunningPersonalRecord]]:
        # Snapshot prior bests before inserting, so the new run is never
        # compared against itself.
        prior_runs = self.list_runs()
        prior_longest_km = max((item.distance_km for item in prior_runs), default=None)
        prior_comparable_heart_rates = [
            item.average_heart_rate
            for item in prior_runs
            if abs(item.average_pace_seconds_per_km - average_pace_seconds_per_km)
            <= LOWEST_HEART_RATE_PACE_TOLERANCE_SECONDS_PER_KM
        ]
        prior_lowest_heart_rate_at_pace = (
            min(prior_comparable_heart_rates) if prior_comparable_heart_rates else None
        )

        effort_score = calculate_effort_score(
            run_type=run_type,
            distance_km=distance_km,
            pace_seconds_per_km=average_pace_seconds_per_km,
            average_heart_rate=average_heart_rate,
        )
        with self._session_factory() as session:
            model = RunRecordModel(
                run_date=run_date,
                run_type=run_type,
                distance_km=distance_km,
                average_pace_seconds_per_km=average_pace_seconds_per_km,
                average_heart_rate=average_heart_rate,
                effort_score=effort_score,
            )
            session.add(model)
            session.commit()
            saved_id = model.id

        saved = next(record for record in self.list_runs() if record.id == saved_id)

        records: list[RunningPersonalRecord] = []
        if prior_longest_km is not None and distance_km > prior_longest_km:
            records.append(
                RunningPersonalRecord(
                    record_type="longest_run",
                    value=distance_km,
                    previous_value=prior_longest_km,
                    run_date=run_date,
                )
            )
        if (
            prior_lowest_heart_rate_at_pace is not None
            and average_heart_rate < prior_lowest_heart_rate_at_pace
        ):
            records.append(
                RunningPersonalRecord(
                    record_type="lowest_heart_rate_at_pace",
                    value=float(average_heart_rate),
                    previous_value=float(prior_lowest_heart_rate_at_pace),
                    run_date=run_date,
                    pace_seconds_per_km=average_pace_seconds_per_km,
                )
            )

        return saved, records

    def list_runs(self) -> list[RunRecord]:
        with self._session_factory() as session:
            models = list(
                session.scalars(
                    select(RunRecordModel).order_by(
                        RunRecordModel.run_date.asc(), RunRecordModel.id.asc()
                    )
                )
            )

        fitness = 0.0
        records: list[RunRecord] = []
        for index, model in enumerate(models):
            fitness = (
                model.effort_score
                if index == 0
                else (0.25 * model.effort_score) + (0.75 * fitness)
            )
            records.append(
                RunRecord(
                    id=model.id,
                    run_date=model.run_date,
                    run_type=model.run_type,  # type: ignore[arg-type]
                    distance_km=model.distance_km,
                    average_pace_seconds_per_km=model.average_pace_seconds_per_km,
                    average_heart_rate=model.average_heart_rate,
                    effort_score=round(model.effort_score, 1),
                    fitness_score=round(fitness, 1),
                    created_at=model.created_at,
                )
            )
        return list(reversed(records))
