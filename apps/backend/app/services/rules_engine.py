from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal


Severity = Literal["info", "success", "warning", "critical"]


@dataclass(frozen=True)
class Recommendation:
    rule_id: str
    module: str
    title: str
    message: str
    severity: Severity
    priority: int


class RulesEngine:
    """Small deterministic rules engine used before AI-generated recommendations."""

    def evaluate(
        self,
        *,
        today: date,
        recent_runs: list,
        recent_workouts: list,
    ) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        week_start = today - timedelta(days=6)
        recent_run_count = sum(item.run_date >= week_start for item in recent_runs)
        recent_workout_count = sum(item.workout_date >= week_start for item in recent_workouts)

        latest_run_date = recent_runs[0].run_date if recent_runs else None
        latest_workout_date = recent_workouts[0].workout_date if recent_workouts else None

        if recent_workout_count == 0:
            recommendations.append(
                Recommendation(
                    rule_id="gym.no_workout_7d",
                    module="gym",
                    title="Plan a gym session",
                    message="No gym workout has been logged in the last seven days.",
                    severity="warning",
                    priority=80,
                )
            )
        elif latest_workout_date == today:
            recommendations.append(
                Recommendation(
                    rule_id="gym.completed_today",
                    module="gym",
                    title="Workout completed",
                    message="Today's gym session is logged. Prioritise recovery before another hard session.",
                    severity="success",
                    priority=40,
                )
            )

        if recent_run_count == 0:
            recommendations.append(
                Recommendation(
                    rule_id="running.no_run_7d",
                    module="running",
                    title="Consider an easy run",
                    message="No run has been logged in the last seven days. An easy session could rebuild consistency.",
                    severity="info",
                    priority=55,
                )
            )
        elif recent_run_count >= 5:
            recommendations.append(
                Recommendation(
                    rule_id="running.high_frequency",
                    module="running",
                    title="Running load is high",
                    message=f"{recent_run_count} runs were logged in seven days. Consider an easy or rest day.",
                    severity="warning",
                    priority=75,
                )
            )
        elif latest_run_date == today:
            recommendations.append(
                Recommendation(
                    rule_id="running.completed_today",
                    module="running",
                    title="Run completed",
                    message="Today's run is logged. Keep any additional training easy.",
                    severity="success",
                    priority=35,
                )
            )

        if not recommendations:
            recommendations.append(
                Recommendation(
                    rule_id="system.balanced",
                    module="system",
                    title="Training looks balanced",
                    message="Recent running and gym frequency are within the current baseline rules.",
                    severity="success",
                    priority=20,
                )
            )

        return sorted(recommendations, key=lambda item: item.priority, reverse=True)
