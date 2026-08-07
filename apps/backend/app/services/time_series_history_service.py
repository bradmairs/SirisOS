from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from threading import Lock
from typing import Mapping

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class TimeSeriesObservationModel(Base):
    __tablename__ = "time_series_observations"
    __table_args__ = (
        Index(
            "ix_time_series_observations_series",
            "source",
            "metric",
            "dimensions_key",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(96), index=True)
    metric: Mapped[str] = mapped_column(String(128), index=True)
    dimensions_key: Mapped[str] = mapped_column(Text, default="{}")
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_value: Mapped[str | None] = mapped_column(String(512), nullable=True)


@dataclass(frozen=True)
class TimeSeriesObservation:
    observed_at: datetime
    source: str
    metric: str
    dimensions: dict[str, str]
    numeric_value: float | None
    text_value: str | None


class TimeSeriesHistoryService:
    """Generic persistent history for low-frequency SirisOS observations."""

    def __init__(self) -> None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos",
        )
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        self._write_lock = Lock()
        self._last_recorded: dict[tuple[str, str, str], datetime] = {}

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def record_if_due(
        self,
        *,
        source: str,
        metric: str,
        numeric_value: float | int | None = None,
        text_value: str | None = None,
        dimensions: Mapping[str, object] | None = None,
        observed_at: datetime | None = None,
        minimum_interval_seconds: int = 60,
        retention_days: int = 90,
    ) -> bool:
        if numeric_value is None and text_value is None:
            return False

        now = observed_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        dimensions_key = self._dimensions_key(dimensions)
        series_key = (source, metric, dimensions_key)

        with self._write_lock:
            cached_at = self._last_recorded.get(series_key)
            if cached_at is not None and (now - cached_at).total_seconds() < minimum_interval_seconds:
                return False

            try:
                with self._session_factory() as session:
                    latest = session.scalar(
                        select(TimeSeriesObservationModel)
                        .where(TimeSeriesObservationModel.source == source)
                        .where(TimeSeriesObservationModel.metric == metric)
                        .where(TimeSeriesObservationModel.dimensions_key == dimensions_key)
                        .order_by(TimeSeriesObservationModel.observed_at.desc())
                        .limit(1)
                    )
                    if latest is not None:
                        latest_at = latest.observed_at
                        if latest_at.tzinfo is None:
                            latest_at = latest_at.replace(tzinfo=timezone.utc)
                        self._last_recorded[series_key] = latest_at
                        if (now - latest_at).total_seconds() < minimum_interval_seconds:
                            return False

                    session.add(
                        TimeSeriesObservationModel(
                            observed_at=now,
                            source=source,
                            metric=metric,
                            dimensions_key=dimensions_key,
                            numeric_value=float(numeric_value) if numeric_value is not None else None,
                            text_value=text_value[:512] if text_value is not None else None,
                        )
                    )
                    self._prune(session, now=now, retention_days=retention_days)
                    session.commit()
                self._last_recorded[series_key] = now
                return True
            except Exception:
                return False

    def record_if_changed(
        self,
        *,
        source: str,
        metric: str,
        numeric_value: float | int | None = None,
        text_value: str | None = None,
        dimensions: Mapping[str, object] | None = None,
        observed_at: datetime | None = None,
        retention_days: int = 90,
    ) -> bool:
        """Persist a series only when its value changes.

        This is useful for discrete operational events such as completed backup
        jobs where repeated polling must not create duplicate observations.
        """
        if numeric_value is None and text_value is None:
            return False
        now = observed_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        dimensions_key = self._dimensions_key(dimensions)
        numeric = float(numeric_value) if numeric_value is not None else None
        text = text_value[:512] if text_value is not None else None

        with self._write_lock:
            try:
                with self._session_factory() as session:
                    latest = session.scalar(
                        select(TimeSeriesObservationModel)
                        .where(TimeSeriesObservationModel.source == source)
                        .where(TimeSeriesObservationModel.metric == metric)
                        .where(TimeSeriesObservationModel.dimensions_key == dimensions_key)
                        .order_by(TimeSeriesObservationModel.observed_at.desc())
                        .limit(1)
                    )
                    if latest is not None and latest.numeric_value == numeric and latest.text_value == text:
                        return False
                    session.add(
                        TimeSeriesObservationModel(
                            observed_at=now,
                            source=source,
                            metric=metric,
                            dimensions_key=dimensions_key,
                            numeric_value=numeric,
                            text_value=text,
                        )
                    )
                    self._prune(session, now=now, retention_days=retention_days)
                    session.commit()
                return True
            except Exception:
                return False

    def history(
        self,
        *,
        source: str,
        metric: str,
        dimensions: Mapping[str, object] | None = None,
        hours: int = 24,
        limit: int = 720,
    ) -> list[TimeSeriesObservation]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        dimensions_key = self._dimensions_key(dimensions) if dimensions is not None else None
        query = (
            select(TimeSeriesObservationModel)
            .where(TimeSeriesObservationModel.source == source)
            .where(TimeSeriesObservationModel.metric == metric)
            .where(TimeSeriesObservationModel.observed_at >= cutoff)
        )
        if dimensions_key is not None:
            query = query.where(TimeSeriesObservationModel.dimensions_key == dimensions_key)
        query = query.order_by(TimeSeriesObservationModel.observed_at.asc()).limit(limit)

        with self._session_factory() as session:
            rows = list(session.scalars(query))

        return [
            TimeSeriesObservation(
                observed_at=row.observed_at,
                source=row.source,
                metric=row.metric,
                dimensions=self._parse_dimensions(row.dimensions_key),
                numeric_value=row.numeric_value,
                text_value=row.text_value,
            )
            for row in rows
        ]

    def _prune(self, session: object, *, now: datetime, retention_days: int) -> None:
        cutoff = now - timedelta(days=retention_days)
        session.execute(
            delete(TimeSeriesObservationModel).where(
                TimeSeriesObservationModel.observed_at < cutoff
            )
        )

    @staticmethod
    def _dimensions_key(dimensions: Mapping[str, object] | None) -> str:
        normalised = {
            str(key): str(value)
            for key, value in sorted((dimensions or {}).items(), key=lambda item: str(item[0]))
        }
        return json.dumps(normalised, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _parse_dimensions(value: str) -> dict[str, str]:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if not isinstance(decoded, dict):
            return {}
        return {str(key): str(item) for key, item in decoded.items()}


history_service = TimeSeriesHistoryService()
history_service.initialise()
