from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

HEALTH_SUMMARY_BASELINE_DAYS = 14
MIN_BASELINE_SAMPLES = 3
SNAPSHOT_FRESHNESS = timedelta(hours=48)


class Base(DeclarativeBase):
    pass


class HealthMetricSampleModel(Base):
    """One Apple Health metric reading. Content-addressed so re-sending the same
    window from Health Auto Export never produces duplicate rows, while a
    revised value (e.g. sleep reprocessed by Apple Health) lands as a new row."""

    __tablename__ = "health_metric_samples"

    sample_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    metric_type: Mapped[str] = mapped_column(String(80), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HealthWorkoutModel(Base):
    """One Apple Health workout, upserted by Health Auto Export's workout id so
    a finalised/amended workout replaces the earlier version instead of duplicating."""

    __tablename__ = "health_workouts"

    external_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    workout_type: Mapped[str] = mapped_column(String(80))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    active_energy_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HealthImportReceiptModel(Base):
    """Provenance record for one Health Auto Export POST, for /health/status and debugging."""

    __tablename__ = "health_import_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    automation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    automation_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metric_samples_received: Mapped[int] = mapped_column(Integer, default=0)
    workouts_received: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


@dataclass(frozen=True)
class HealthIngestResult:
    accepted: bool
    metric_samples_received: int
    workouts_received: int
    error: str | None


@dataclass(frozen=True)
class HealthIngestStatus:
    last_sync: datetime | None
    records_received: int
    last_error: str | None


@dataclass(frozen=True)
class HealthMetricSummary:
    metric_type: str
    unit: str | None
    latest_value: float
    latest_timestamp: datetime
    baseline_average: float | None
    baseline_ratio: float | None
    baseline_sample_count: int


@dataclass(frozen=True)
class HealthSnapshotMetric:
    name: str
    value: float
    unit: str | None
    date: str | None


@dataclass(frozen=True)
class HealthSnapshot:
    available: bool
    endpoint_configured: bool
    tools: list[str]
    metrics: list[HealthSnapshotMetric]
    error: str | None


def _as_float(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("qty", value.get("value"))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_unit(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("units") or value.get("unit")
    return None


def _parse_timestamp(raw: Any) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    # Health Auto Export emits "YYYY-MM-DD HH:MM:SS +ZZZZ"; ISO 8601 wants a "T".
    if " " in text and "T" not in text:
        date_part, _, remainder = text.partition(" ")
        text = f"{date_part}T{remainder}"
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _sample_key(*, metric_type: str, timestamp: datetime, source: str | None, value: float, unit: str | None) -> str:
    identity = f"{metric_type}|{timestamp.isoformat()}|{source or ''}|{value}|{unit or ''}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class HealthIngestService:
    """Canonical store for Apple Health data pushed by Health Auto Export.

    Health Auto Export cannot stay running while the iPhone is backgrounded, so
    it is treated as an unattended push source: this service accepts JSON export
    v2 payloads, normalises them into `health_metric_samples`/`health_workouts`,
    and keeps a receipt trail so /health/status can report sync health.
    """

    def __init__(self, database_url: str | None = None) -> None:
        resolved_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://sirisos:change-me@postgres:5432/sirisos",
        )
        self._engine = create_engine(resolved_url, pool_pre_ping=True)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def initialise(self) -> None:
        Base.metadata.create_all(self._engine)

    def ingest(
        self,
        payload: dict[str, Any],
        *,
        automation_id: str | None = None,
        automation_name: str | None = None,
        session_id: str | None = None,
    ) -> HealthIngestResult:
        now = datetime.now(timezone.utc)
        try:
            samples = self._parse_metric_samples(payload, imported_at=now)
            workouts = self._parse_workouts(payload, imported_at=now)
        except Exception as exc:  # Malformed payloads must not crash the ingest endpoint.
            self._record_receipt(
                received_at=now,
                automation_id=automation_id,
                automation_name=automation_name,
                session_id=session_id,
                metric_samples_received=0,
                workouts_received=0,
                error=str(exc),
            )
            return HealthIngestResult(False, 0, 0, str(exc))

        with self._sessions() as session:
            for sample in samples:
                if session.get(HealthMetricSampleModel, sample.sample_key) is None:
                    session.add(sample)
            for workout in workouts:
                existing = session.get(HealthWorkoutModel, workout.external_id)
                if existing is None:
                    session.add(workout)
                else:
                    existing.workout_type = workout.workout_type
                    existing.start_time = workout.start_time
                    existing.end_time = workout.end_time
                    existing.duration_seconds = workout.duration_seconds
                    existing.distance_m = workout.distance_m
                    existing.active_energy_kcal = workout.active_energy_kcal
                    existing.avg_hr = workout.avg_hr
                    existing.max_hr = workout.max_hr
                    existing.source = workout.source
                    existing.imported_at = workout.imported_at
            session.commit()

        self._record_receipt(
            received_at=now,
            automation_id=automation_id,
            automation_name=automation_name,
            session_id=session_id,
            metric_samples_received=len(samples),
            workouts_received=len(workouts),
            error=None,
        )
        return HealthIngestResult(True, len(samples), len(workouts), None)

    def status(self) -> HealthIngestStatus:
        with self._sessions() as session:
            latest = session.scalar(
                select(HealthImportReceiptModel).order_by(
                    HealthImportReceiptModel.received_at.desc(),
                    HealthImportReceiptModel.id.desc(),
                )
            )
            records_received = int(session.scalar(select(func.count()).select_from(HealthMetricSampleModel)) or 0)
            records_received += int(session.scalar(select(func.count()).select_from(HealthWorkoutModel)) or 0)
        return HealthIngestStatus(
            last_sync=latest.received_at if latest else None,
            records_received=records_received,
            last_error=latest.error if latest else None,
        )

    def summary(self, *, baseline_days: int = HEALTH_SUMMARY_BASELINE_DAYS) -> list[HealthMetricSummary]:
        # One row per metric_type: the latest reading, plus a trailing baseline
        # average computed from samples strictly *before* the latest reading's
        # own day -- so a metric is never compared against itself, matching the
        # same principle ADR 066/067/069 already apply to gym/running data.
        # Requires MIN_BASELINE_SAMPLES before showing a ratio, same reasoning
        # as TrainingLoadService's MIN_BASELINE_WEEKS: too little history to
        # call anything "typical" yet.
        with self._sessions() as session:
            metric_types = session.scalars(
                select(HealthMetricSampleModel.metric_type).distinct()
            ).all()

            summaries: list[HealthMetricSummary] = []
            for metric_type in metric_types:
                latest = session.scalar(
                    select(HealthMetricSampleModel)
                    .where(HealthMetricSampleModel.metric_type == metric_type)
                    .order_by(HealthMetricSampleModel.timestamp.desc())
                    .limit(1)
                )
                if latest is None:
                    continue

                latest_day_start = latest.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                baseline_window_start = latest_day_start - timedelta(days=baseline_days)
                baseline_rows = session.scalars(
                    select(HealthMetricSampleModel.value).where(
                        HealthMetricSampleModel.metric_type == metric_type,
                        HealthMetricSampleModel.timestamp >= baseline_window_start,
                        HealthMetricSampleModel.timestamp < latest_day_start,
                    )
                ).all()

                baseline_average: float | None = None
                baseline_ratio: float | None = None
                if len(baseline_rows) >= MIN_BASELINE_SAMPLES:
                    baseline_average = round(sum(baseline_rows) / len(baseline_rows), 2)
                    if baseline_average != 0:
                        baseline_ratio = round((latest.value / baseline_average) * 100, 1)

                summaries.append(
                    HealthMetricSummary(
                        metric_type=metric_type,
                        unit=latest.unit,
                        latest_value=latest.value,
                        latest_timestamp=latest.timestamp,
                        baseline_average=baseline_average,
                        baseline_ratio=baseline_ratio,
                        baseline_sample_count=len(baseline_rows),
                    )
                )

        return sorted(summaries, key=lambda item: item.metric_type)

    def snapshot(self) -> HealthSnapshot:
        # Sourced from ingested samples rather than a live call out to a phone-hosted
        # server (the old Health Auto Export MCP integration) -- the same rows that
        # /health/ingest writes and /health/summary reads from, so any pusher (native
        # HealthKit sync or, historically, Health Auto Export) lights this up the same way.
        with self._sessions() as session:
            metric_types = session.scalars(
                select(HealthMetricSampleModel.metric_type).distinct()
            ).all()
            if not metric_types:
                return HealthSnapshot(False, False, [], [], "No Apple Health data has been synced yet.")

            latest_rows = [
                row
                for metric_type in metric_types
                if (
                    row := session.scalar(
                        select(HealthMetricSampleModel)
                        .where(HealthMetricSampleModel.metric_type == metric_type)
                        .order_by(HealthMetricSampleModel.timestamp.desc())
                        .limit(1)
                    )
                )
                is not None
            ]

        latest_rows.sort(key=lambda row: row.metric_type)
        most_recent = max((row.timestamp for row in latest_rows), default=None)
        # SQLite (used in local dev/tests) drops tzinfo on round-trip even for a
        # DateTime(timezone=True) column, unlike Postgres; every write path here
        # stores UTC, so a naive value is always UTC.
        if most_recent is not None and most_recent.tzinfo is None:
            most_recent = most_recent.replace(tzinfo=timezone.utc)
        is_fresh = most_recent is not None and (
            datetime.now(timezone.utc) - most_recent <= SNAPSHOT_FRESHNESS
        )

        return HealthSnapshot(
            available=is_fresh,
            endpoint_configured=True,
            tools=[row.metric_type for row in latest_rows],
            metrics=[
                HealthSnapshotMetric(
                    name=row.metric_type,
                    value=row.value,
                    unit=row.unit,
                    date=row.timestamp.isoformat(),
                )
                for row in latest_rows
            ],
            error=None if is_fresh else "No Apple Health data synced in the last 48 hours.",
        )

    def _record_receipt(
        self,
        *,
        received_at: datetime,
        automation_id: str | None,
        automation_name: str | None,
        session_id: str | None,
        metric_samples_received: int,
        workouts_received: int,
        error: str | None,
    ) -> None:
        with self._sessions() as session:
            session.add(
                HealthImportReceiptModel(
                    received_at=received_at,
                    automation_id=automation_id,
                    automation_name=automation_name,
                    session_id=session_id,
                    metric_samples_received=metric_samples_received,
                    workouts_received=workouts_received,
                    error=error,
                )
            )
            session.commit()

    @staticmethod
    def _parse_metric_samples(payload: dict[str, Any], *, imported_at: datetime) -> list[HealthMetricSampleModel]:
        metrics = payload.get("data", payload).get("metrics", [])
        if not isinstance(metrics, list):
            return []
        samples: list[HealthMetricSampleModel] = []
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            metric_type = str(metric.get("name") or "unknown")
            unit = metric.get("units") or metric.get("unit")
            entries = metric.get("data")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                timestamp = _parse_timestamp(entry.get("date") or entry.get("timestamp"))
                value = _as_float(entry)
                if timestamp is None or value is None:
                    continue
                entry_unit = entry.get("units") or entry.get("unit") or unit
                source = entry.get("source")
                key = _sample_key(
                    metric_type=metric_type,
                    timestamp=timestamp,
                    source=source,
                    value=value,
                    unit=entry_unit,
                )
                samples.append(
                    HealthMetricSampleModel(
                        sample_key=key,
                        metric_type=metric_type,
                        timestamp=timestamp,
                        value=value,
                        unit=entry_unit,
                        source=source,
                        imported_at=imported_at,
                    )
                )
        return samples

    @staticmethod
    def _parse_workouts(payload: dict[str, Any], *, imported_at: datetime) -> list[HealthWorkoutModel]:
        workouts = payload.get("data", payload).get("workouts", [])
        if not isinstance(workouts, list):
            return []
        records: list[HealthWorkoutModel] = []
        for workout in workouts:
            if not isinstance(workout, dict):
                continue
            external_id = str(workout.get("id") or workout.get("workoutId") or "")
            start_time = _parse_timestamp(workout.get("start") or workout.get("startDate"))
            if not external_id or start_time is None:
                continue
            end_time = _parse_timestamp(workout.get("end") or workout.get("endDate"))
            duration = _as_float(workout.get("duration"))
            distance = _as_float(workout.get("distance"))
            active_energy = _as_float(workout.get("activeEnergyBurned") or workout.get("activeEnergy"))
            avg_hr, max_hr = HealthIngestService._heart_rate_bounds(workout)
            records.append(
                HealthWorkoutModel(
                    external_id=external_id,
                    workout_type=str(workout.get("name") or workout.get("workoutActivityType") or "unknown"),
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    distance_m=distance,
                    active_energy_kcal=active_energy,
                    avg_hr=avg_hr,
                    max_hr=max_hr,
                    source=workout.get("source"),
                    imported_at=imported_at,
                )
            )
        return records

    @staticmethod
    def _heart_rate_bounds(workout: dict[str, Any]) -> tuple[float | None, float | None]:
        avg = _as_float(workout.get("avgHeartRate") or workout.get("averageHeartRate"))
        peak = _as_float(workout.get("maxHeartRate") or workout.get("peakHeartRate"))
        if avg is not None or peak is not None:
            return avg, peak
        samples = workout.get("heartRateData")
        if not isinstance(samples, list) or not samples:
            return None, None
        values = [v for v in (_as_float(item) for item in samples) if v is not None]
        if not values:
            return None, None
        return sum(values) / len(values), max(values)
