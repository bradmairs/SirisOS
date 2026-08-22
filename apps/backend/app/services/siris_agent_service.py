from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from typing import Any

from app.services.achievement_service import AchievementService
from app.services.docker_service import DockerMonitor
from app.services.gym_service import GymService
from app.services.health_ingest_service import HealthIngestService
from app.services.homelab_alert_service import HomelabAlertService
from app.services.host_metrics_service import HostMetricsCollector
from app.services.knowledge_service import KnowledgeService
from app.services.ollama_service import chat_client
from app.services.project_service import ProjectService
from app.services.readiness_service import ReadinessService
from app.services.running_service import RunningService
from app.services.training_conflict_service import TrainingConflictService
from app.services.training_level_service import TrainingLevelService
from app.services.training_load_service import TrainingLoadService

# Ask Siris (ADR 071/081) is a fixed set of regex-matched question shapes,
# each answered by exactly the deterministic call that answers it -- fast,
# zero Ollama round-trips, but only ever the questions it was built to
# recognise. This is the tool-using counterpart: Ollama itself decides which
# of these same underlying services to call based on a free-text question,
# genuinely "ask anything" within what SirisOS actually knows -- but every
# fact it states still has to come from a tool call, never its own training
# data. v1 scoped to Training + Health; Homelab (Docker status, host
# metrics) added in v2, reusing the same already-shipped deterministic
# services the Homelab dashboard cards already call. Homelab alerts followed
# once their scoring logic was itself extracted out of the route handler
# into HomelabAlertService (ADR 094). Knowledge and Projects followed the
# same pattern once KnowledgeService/ProjectService existed to wrap
# (ADR 096) -- both previously lived directly in API route handlers with
# no reusable service-layer object.

MAX_TOOL_ITERATIONS = 5
DEFAULT_LIST_LIMIT = 5
MAX_LIST_LIMIT = 20

REFUSAL_MESSAGE = (
    "I can only answer questions about your own SirisOS training, health, homelab, knowledge "
    "and projects data."
)

SIRIS_AGENT_SYSTEM_PROMPT = (
    "You are Siris, a personal training, health, homelab, knowledge and projects assistant "
    "inside SirisOS. You can ONLY answer questions about the athlete's own SirisOS data -- "
    "strength, running, gym workouts, muscle recovery, Apple Health metrics, "
    "readiness/recovery score, achievements, Docker container status, server/host resource "
    "usage, their personal Knowledge notes, and their Projects. You have tools that look up "
    "that real data.\n\n"
    "Rules, no exceptions:\n"
    "1. If the question is not about the athlete's own training, health, homelab, knowledge "
    "or projects data -- general knowledge, world facts, anything none of your tools can "
    f"answer -- do not call any tool. Reply with exactly this sentence: \"{REFUSAL_MESSAGE}\"\n"
    "2. THE MOMENT A TOOL RETURNS A RESULT, YOU MUST ANSWER USING THAT RESULT. This "
    "overrides everything else, including rule 1 -- the refusal sentence is ONLY for the "
    "instant before you've called any tool. A tool call happening at all means the "
    "question was in scope; do not re-judge that after the fact and refuse anyway. This "
    "is a real, observed failure mode: do not repeat it.\n"
    "3. Call the tool(s) that answer a question before saying anything factual. Never "
    "state a number, date, name or result that a tool did not return.\n"
    "4. Only describe what a tool actually returned. Do not rename, relabel or blend "
    "one tool's numbers into a different metric -- weekly training load is not the "
    "same thing as training level; if asked about both, call both tools.\n"
    "5. If a tool result says data is missing or insufficient, report that honestly -- "
    "do not fill the gap with a guess.\n"
    "6. search_knowledge's top_result_content field is the real text of the best-matching "
    "note -- if it's non-null, answer from it directly, in the same turn. Do not guess "
    "what a note says from its title, and do not call read_knowledge_note again for the "
    "same note you already have top_result_content for -- that content already IS the "
    "note. Only call read_knowledge_note if the athlete specifically wants a different "
    "hit than the top one, or top_result_content is null.\n"
    "7. search_knowledge takes only {\"query\": ...} and read_knowledge_note takes only "
    "{\"path\": ...} -- never merge the two calls' arguments together.\n"
    "Example: asked \"what's the weather like\", you have no weather tool, so reply "
    f"with exactly \"{REFUSAL_MESSAGE}\" rather than guessing or calling an unrelated tool.\n\n"
    "Keep answers concise -- a few sentences, not a report."
)


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _clamp_limit(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LIST_LIMIT
    return max(1, min(MAX_LIST_LIMIT, value))


@dataclass(frozen=True)
class SirisAgentAnswer:
    answer: str
    tools_used: list[str] = field(default_factory=list)
    available: bool = True


_LIMIT_PARAMETER = {
    "limit": {
        "type": "integer",
        "description": "How many to return, most recent first (default 5, max 20).",
    }
}

_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_strength_score",
            "description": (
                "Current strength: each tagged exercise's estimated 1RM versus that same "
                "exercise's own all-time peak, self-relative only -- never compared to "
                "another person or an external standard. Includes an overall score and a "
                "per-muscle-group breakdown."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_training_level",
            "description": (
                "Composite training level across Strength, Endurance and Consistency "
                "dimensions, each self-relative to the athlete's own history."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_muscle_group_fatigue",
            "description": (
                "Estimated fatigue per muscle group (chest, back, legs, shoulders, arms, "
                "core) -- how recently and heavily trained, and roughly when each is "
                "estimated to be ready to train again. An estimate, not a physiological "
                "measurement."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_training_load",
            "description": (
                "This week's combined running and gym training load versus the athlete's "
                "own trailing baseline, with a plain-English assessment."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_runs",
            "description": "The athlete's most recently logged runs, most recent first.",
            "parameters": {"type": "object", "properties": _LIMIT_PARAMETER, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_workouts",
            "description": "The athlete's most recently logged gym workouts, most recent first.",
            "parameters": {"type": "object", "properties": _LIMIT_PARAMETER, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_health_summary",
            "description": (
                "Ingested Apple Health metrics (HRV, resting heart rate, steps, sleep, "
                "etc.) with today's total or latest reading versus the athlete's own "
                "trailing 14-day baseline."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_training_conflict_today",
            "description": (
                "Whether today's recovery (HRV/resting heart rate) looks reduced versus "
                "the athlete's own baseline, and whether they've already trained today."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_achievements",
            "description": (
                "The athlete's evidence-backed training achievements -- which are "
                "unlocked, and progress toward the ones that aren't."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_docker_status",
            "description": (
                "Status of every Docker container on the homelab server -- how many are "
                "running, stopped, or unhealthy, and each container's name, state and "
                "health."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_host_metrics",
            "description": (
                "The homelab server's own resource usage right now -- CPU, memory and "
                "disk percent used, load average, and uptime."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_readiness_score",
            "description": (
                "Today's readiness/recovery score (0-100), self-relative to the "
                "athlete's own trailing baseline -- driven by heart rate "
                "variability and last night's sleep versus their own norm. "
                "100 means fully at or above their own baseline; lower means "
                "below it. Null if not enough HRV/sleep history has synced yet."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_homelab_alerts",
            "description": (
                "Active homelab alerts right now -- high host CPU/memory/disk usage, "
                "Docker monitoring unavailable, and any container that's unhealthy, "
                "stopped, or has an image update available. Includes an overall "
                "healthy/warning/critical status and counts."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Search the athlete's own Knowledge vault (personal notes) by keyword. "
                "Returns matching notes' titles/paths/tags, PLUS the full real text of the "
                "best-matching note in top_result_content -- that field already answers "
                "most 'what does my note about X say' questions on its own. Only call "
                "read_knowledge_note separately if the athlete wants a DIFFERENT hit than "
                "the top one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword or phrase to search for."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_knowledge_note",
            "description": (
                "Read one Knowledge note's full content by its path, exactly as returned by "
                "search_knowledge. Use this to actually answer a question from a note's text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The note's path, from a search_knowledge hit."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_projects",
            "description": "The athlete's own SirisOS projects -- name, kind, status and tags for each.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_project",
            "description": "Whichever project is currently marked as active/in-focus in SirisOS, if any.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


class SirisAgentService:
    def __init__(
        self,
        gym_service: GymService | None = None,
        running_service: RunningService | None = None,
        health_service: HealthIngestService | None = None,
        training_load_service: TrainingLoadService | None = None,
        training_conflict_service: TrainingConflictService | None = None,
        training_level_service: TrainingLevelService | None = None,
        achievement_service: AchievementService | None = None,
        docker_monitor: DockerMonitor | None = None,
        host_metrics_collector: HostMetricsCollector | None = None,
        homelab_alert_service: HomelabAlertService | None = None,
        readiness_service: ReadinessService | None = None,
        knowledge_service: KnowledgeService | None = None,
        project_service: ProjectService | None = None,
    ) -> None:
        self._gym_service = gym_service or GymService()
        self._running_service = running_service or RunningService()
        self._health_service = health_service or HealthIngestService()
        self._readiness_service = readiness_service or ReadinessService(health_service=self._health_service)
        self._training_load_service = training_load_service or TrainingLoadService(
            running_service=self._running_service, gym_service=self._gym_service
        )
        self._training_conflict_service = training_conflict_service or TrainingConflictService(
            running_service=self._running_service,
            gym_service=self._gym_service,
            health_service=self._health_service,
        )
        self._training_level_service = training_level_service or TrainingLevelService(
            gym_service=self._gym_service, running_service=self._running_service
        )
        self._achievement_service = achievement_service or AchievementService(
            running_service=self._running_service, gym_service=self._gym_service
        )
        self._docker_monitor = docker_monitor or DockerMonitor()
        self._host_metrics_collector = host_metrics_collector or HostMetricsCollector()
        self._homelab_alert_service = homelab_alert_service or HomelabAlertService(
            host_metrics_collector=self._host_metrics_collector, docker_monitor=self._docker_monitor
        )
        self._knowledge_service = knowledge_service or KnowledgeService()
        self._project_service = project_service or ProjectService()
        self._dispatch = {
            "get_strength_score": self._get_strength_score,
            "get_training_level": self._get_training_level,
            "get_muscle_group_fatigue": self._get_muscle_group_fatigue,
            "get_weekly_training_load": self._get_weekly_training_load,
            "get_recent_runs": self._get_recent_runs,
            "get_recent_workouts": self._get_recent_workouts,
            "get_health_summary": self._get_health_summary,
            "get_training_conflict_today": self._get_training_conflict_today,
            "get_achievements": self._get_achievements,
            "get_readiness_score": self._get_readiness_score,
            "get_docker_status": self._get_docker_status,
            "get_host_metrics": self._get_host_metrics,
            "get_homelab_alerts": self._get_homelab_alerts,
            "search_knowledge": self._search_knowledge,
            "read_knowledge_note": self._read_knowledge_note,
            "get_projects": self._get_projects,
            "get_current_project": self._get_current_project,
        }

    async def ask(self, messages: list[dict[str, Any]]) -> SirisAgentAnswer:
        if not chat_client.enabled:
            return SirisAgentAnswer(
                answer=(
                    "Siris needs Ollama configured to answer open-ended questions -- "
                    "ask a fixed question in Coach's Ask Siris box instead, or set "
                    "OLLAMA_URL/SIRISOS_OLLAMA_CHAT_MODEL to enable this."
                ),
                tools_used=[],
                available=False,
            )

        conversation: list[dict[str, Any]] = [
            {"role": "system", "content": SIRIS_AGENT_SYSTEM_PROMPT},
            *messages,
        ]
        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ITERATIONS):
            result = await chat_client.chat(messages=conversation, tools=_TOOL_DEFINITIONS)
            if result is None:
                return SirisAgentAnswer(
                    answer="Siris couldn't reach Ollama just now -- try again in a moment.",
                    tools_used=tools_used,
                    available=False,
                )
            if not result.tool_calls:
                return SirisAgentAnswer(
                    answer=result.content or "Siris didn't have anything to add.",
                    tools_used=tools_used,
                    available=True,
                )

            conversation.append(
                {
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": [
                        {"function": {"name": call.name, "arguments": call.arguments}}
                        for call in result.tool_calls
                    ],
                }
            )
            for call in result.tool_calls:
                handler = self._dispatch.get(call.name)
                if handler is None:
                    tool_result: object = {"error": f"Unknown tool '{call.name}'."}
                else:
                    try:
                        tool_result = handler(call.arguments)
                    except Exception as exc:  # noqa: BLE001 - a tool failure must not crash the turn
                        tool_result = {"error": f"Could not fetch this: {exc}"}
                    tools_used.append(call.name)
                conversation.append(
                    {"role": "tool", "content": json.dumps(_jsonable(tool_result)), "name": call.name}
                )

        return SirisAgentAnswer(
            answer=(
                "Siris checked several things but couldn't settle on an answer -- try "
                "asking a more specific question."
            ),
            tools_used=tools_used,
            available=True,
        )

    def _get_strength_score(self, _arguments: dict[str, Any]) -> object:
        return self._gym_service.strength_score()

    def _get_training_level(self, _arguments: dict[str, Any]) -> object:
        return self._training_level_service.training_level()

    def _get_muscle_group_fatigue(self, _arguments: dict[str, Any]) -> object:
        return self._gym_service.muscle_group_fatigue()

    def _get_weekly_training_load(self, _arguments: dict[str, Any]) -> object:
        return self._training_load_service.weekly_load()

    def _get_recent_runs(self, arguments: dict[str, Any]) -> object:
        limit = _clamp_limit(arguments.get("limit"))
        return self._running_service.list_runs()[:limit]

    def _get_recent_workouts(self, arguments: dict[str, Any]) -> object:
        limit = _clamp_limit(arguments.get("limit"))
        workouts = self._gym_service.list_workouts()[:limit]
        return [
            {
                "id": workout.id,
                "workout_date": workout.workout_date,
                "name": workout.name,
                "notes": workout.notes,
                "total_volume_kg": workout.total_volume_kg,
                "sets": [
                    {
                        "exercise": item.exercise,
                        "weight_kg": item.weight_kg,
                        "reps": item.reps,
                        "rir": item.rir,
                        "volume_kg": item.volume_kg,
                    }
                    for item in workout.sets
                ],
            }
            for workout in workouts
        ]

    def _get_health_summary(self, _arguments: dict[str, Any]) -> object:
        return self._health_service.summary()

    def _get_training_conflict_today(self, _arguments: dict[str, Any]) -> object:
        return self._training_conflict_service.check()

    def _get_achievements(self, _arguments: dict[str, Any]) -> object:
        return self._achievement_service.list_achievements()

    def _get_readiness_score(self, _arguments: dict[str, Any]) -> object:
        return self._readiness_service.today()

    def _get_docker_status(self, _arguments: dict[str, Any]) -> object:
        return self._docker_monitor.collect()

    def _get_host_metrics(self, _arguments: dict[str, Any]) -> object:
        return self._host_metrics_collector.collect()

    def _get_homelab_alerts(self, _arguments: dict[str, Any]) -> object:
        return self._homelab_alert_service.get_summary()

    def _search_knowledge(self, arguments: dict[str, Any]) -> object:
        # Live testing against a real (small, local) model found it
        # unreliable at chaining search_knowledge -> read_knowledge_note
        # even with an explicit rule and worked example -- it would often
        # stop after search_knowledge and either fabricate an answer from
        # the title alone or refuse. Rather than keep depending on that
        # chain being followed, the best-matching hit's real content is
        # included directly in this result, so the common case (asking
        # about the obvious top match) is grounded in one call regardless
        # of whether the model follows up. read_knowledge_note still exists
        # for reading a *different* hit than the top one.
        query = str(arguments.get("query") or "").strip()
        if not query:
            return {"error": "search_knowledge needs a non-empty query."}
        result = self._knowledge_service.search(query, limit=DEFAULT_LIST_LIMIT)
        if not result.hits:
            return result
        top_result_content = self._knowledge_service.read_note(result.hits[0].path)
        return {
            "query": result.query,
            "hits": result.hits,
            "top_result_content": top_result_content,
        }

    def _read_knowledge_note(self, arguments: dict[str, Any]) -> object:
        path = str(arguments.get("path") or "").strip()
        if path:
            note = self._knowledge_service.read_note(path)
            if note is not None:
                return note
        # Observed live: a small model sometimes merges search_knowledge's
        # "query" into this call instead of a real path (even passing the
        # other tool's own name as "path"). Rather than error out on a call
        # that was clearly trying to find real content, fall back to
        # searching with whatever text it did give and reading the top hit
        # -- a generically useful recovery, not specific to any one garbled
        # value, and harmless when the fallback text genuinely matches
        # nothing (falls through to the same honest error below).
        fallback_query = str(arguments.get("query") or "").strip() or path
        if fallback_query:
            hits = self._knowledge_service.search(fallback_query, limit=1).hits
            if hits:
                note = self._knowledge_service.read_note(hits[0].path)
                if note is not None:
                    return note
        return {"error": f"No knowledge note found at '{path or fallback_query}'."}

    def _get_projects(self, _arguments: dict[str, Any]) -> object:
        return self._project_service.list_projects()

    def _get_current_project(self, _arguments: dict[str, Any]) -> object:
        return self._project_service.current_project()
