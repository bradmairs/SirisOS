from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.services.gym_service import GymService
from app.services.health_ingest_service import HEALTH_SUMMARY_BASELINE_DAYS, HealthIngestService, to_local_date
from app.services.running_service import RunningService

# A "conflict" is deliberately narrow for v1: a recovery metric (HRV/resting
# heart rate) reading notably worse than the athlete's own trailing baseline
# on the reference day a session was also logged -- reusing
# HealthIngestService.summary() (ADR 072) exactly as computed there, no new
# inference heuristics (no exercise-name/workout-name guessing, no
# run-intensity proxy). If either metric isn't ingested yet, doesn't have
# enough baseline history, or hasn't synced for the reference day, this says
# so plainly rather than guessing from stale or incomplete data.
HRV_LOW_RATIO_THRESHOLD = 85.0
RESTING_HR_HIGH_RATIO_THRESHOLD = 110.0

_HRV_METRIC_TYPES = {"heart_rate_variability", "hrv"}
_RESTING_HR_METRIC_TYPES = {"resting_heart_rate", "resting_hr"}
_BASELINE_LABEL = f"{HEALTH_SUMMARY_BASELINE_DAYS}-day"


@dataclass(frozen=True)
class TrainingConflictCheck:
    reference_date: date
    status: str  # "insufficient_data" | "clear" | "reduced_recovery" | "conflict"
    reasons: list[str]
    trained: bool
    session_summary: str | None
    guidance: str


class TrainingConflictService:
    def __init__(
        self,
        running_service: RunningService | None = None,
        gym_service: GymService | None = None,
        health_service: HealthIngestService | None = None,
    ) -> None:
        self._running_service = running_service or RunningService()
        self._gym_service = gym_service or GymService()
        self._health_service = health_service or HealthIngestService()

    def check(self, *, reference_date: date | None = None) -> TrainingConflictCheck:
        # date.today() would use the server process's own system timezone
        # (typically UTC in a Docker container) rather than the athlete's --
        # up to half of every Melbourne day that would silently disagree
        # with to_local_date() below, exactly the class of bug this method
        # exists to avoid.
        reference_date = reference_date or to_local_date(datetime.now(timezone.utc))
        summaries = self._health_service.summary()
        hrv = self._for_reference_day(_HRV_METRIC_TYPES, summaries, reference_date)
        resting_hr = self._for_reference_day(_RESTING_HR_METRIC_TYPES, summaries, reference_date)

        reasons: list[str] = []
        has_signal = False
        if hrv is not None and hrv.baseline_ratio is not None:
            has_signal = True
            if hrv.baseline_ratio < HRV_LOW_RATIO_THRESHOLD:
                reasons.append(f"HRV is {hrv.baseline_ratio:g}% of your {_BASELINE_LABEL} baseline")
        if resting_hr is not None and resting_hr.baseline_ratio is not None:
            has_signal = True
            if resting_hr.baseline_ratio > RESTING_HR_HIGH_RATIO_THRESHOLD:
                reasons.append(
                    f"resting heart rate is {resting_hr.baseline_ratio:g}% of your {_BASELINE_LABEL} baseline"
                )

        session_summary = self._session_summary(reference_date)
        trained = session_summary is not None

        if not has_signal:
            return TrainingConflictCheck(
                reference_date=reference_date,
                status="insufficient_data",
                reasons=[],
                trained=trained,
                session_summary=session_summary,
                guidance=(
                    "Not enough synced recovery data for this day yet -- "
                    "keep syncing Health Auto Export and this will fill in."
                ),
            )

        if not reasons:
            return TrainingConflictCheck(
                reference_date=reference_date,
                status="clear",
                reasons=[],
                trained=trained,
                session_summary=session_summary,
                guidance="Recovery looks normal today.",
            )

        if not trained:
            return TrainingConflictCheck(
                reference_date=reference_date,
                status="reduced_recovery",
                reasons=reasons,
                trained=False,
                session_summary=None,
                guidance=(
                    f"Recovery is reduced today ({'; '.join(reasons)}) -- "
                    "good day to keep it light if you were considering training."
                ),
            )

        return TrainingConflictCheck(
            reference_date=reference_date,
            status="conflict",
            reasons=reasons,
            trained=True,
            session_summary=session_summary,
            guidance=(
                f"Recovery looks reduced today ({'; '.join(reasons)}) and you logged "
                f"{session_summary} -- consider dialling back intensity or taking extra rest."
            ),
        )

    @staticmethod
    def _for_reference_day(metric_types: set[str], summaries, reference_date: date):
        item = next((candidate for candidate in summaries if candidate.metric_type in metric_types), None)
        if item is None or to_local_date(item.latest_timestamp) != reference_date:
            return None
        return item

    def _session_summary(self, reference_date: date) -> str | None:
        workouts = [
            workout
            for workout in self._gym_service.list_workouts()
            if workout.workout_date == reference_date
        ]
        runs = [run for run in self._running_service.list_runs() if run.run_date == reference_date]

        parts: list[str] = []
        for workout in workouts:
            parts.append(f"{workout.name} ({workout.total_volume_kg:g} kg)")
        for run in runs:
            parts.append(f"{run.distance_km:g} km run")
        return ", ".join(parts) if parts else None
