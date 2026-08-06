from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import math
import os
from typing import Literal

from sqlalchemy import Date, DateTime, Float, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

RunType = Literal["outdoor", "treadmill"]


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


def calculate_effort_score(
    *,
    run_type: RunType,
    distance_km: float,
    pace_seconds_per_km: int,
    average_heart_rate: int,
) -> float:
    """Return a transparent 0–100 comparative running score.

    The score rewards faster pace at a lower average heart rate, then adds a
    modest distance contribution. It is intended for personal trend tracking,
    not as a medical or physiological assessment.
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
    ) -> RunRecord:
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
        return self.list_runs()[0]

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
            fitness = model.effort_score if index == 0 else (0.25 * model.effort_score) + (0.75 * fitness)
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
