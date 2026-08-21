import asyncio
import json
from datetime import date
from pathlib import Path

from app.services.docker_service import DockerContainer, DockerSummary
from app.services.gym_service import GymService
from app.services.homelab_alert_service import HomelabAlert, HomelabAlertSummary
from app.services.host_metrics_service import HostMetrics
from app.services.ollama_service import OllamaChatResult, OllamaToolCall
from app.services.readiness_service import DailyReadinessPoint
from app.services.running_service import RunningService
from app.services.siris_agent_service import SirisAgentService

# The agent loop composes GymService/RunningService/HealthIngestService/etc,
# unscoped by name -- same fully-isolated-database-per-test reasoning as the
# achievement/coach suites. No real Ollama server exists in this dev
# environment, so every scenario here scripts a fake chat_client -- the real
# HTTP/JSON parsing is covered separately in test_ollama_service.py.


class _FakeChatClient:
    def __init__(self, responses: list[OllamaChatResult | None]) -> None:
        self._responses = list(responses)
        self.enabled = True
        self.calls: list[list[dict]] = []

    async def chat(self, *, messages, tools=None):
        self.calls.append(messages)
        if not self._responses:
            return None
        return self._responses.pop(0)


class _DisabledFakeChatClient:
    enabled = False

    async def chat(self, *, messages, tools=None):  # pragma: no cover - must never be called
        raise AssertionError("chat() should not be called when disabled")


def _build(tmp_path: Path, monkeypatch) -> tuple[GymService, RunningService, SirisAgentService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/siris_agent.db")
    gym = GymService()
    gym.initialise()
    running = RunningService()
    running.initialise()
    return gym, running, SirisAgentService(gym_service=gym, running_service=running)


def test_returns_fixed_message_without_calling_ollama_when_disabled(
    tmp_path: Path, monkeypatch
) -> None:
    _, _, agent = _build(tmp_path, monkeypatch)
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", _DisabledFakeChatClient())

    result = asyncio.run(agent.ask([{"role": "user", "content": "how strong am I?"}]))

    assert result.available is False
    assert "Ollama" in result.answer
    assert result.tools_used == []


def test_returns_direct_answer_when_no_tool_calls_needed(tmp_path: Path, monkeypatch) -> None:
    _, _, agent = _build(tmp_path, monkeypatch)
    fake = _FakeChatClient([OllamaChatResult(content="Hi there!", tool_calls=[])])
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake)

    result = asyncio.run(agent.ask([{"role": "user", "content": "hello"}]))

    assert result.available is True
    assert result.answer == "Hi there!"
    assert result.tools_used == []


def test_dispatches_real_tool_and_feeds_result_back(tmp_path: Path, monkeypatch) -> None:
    gym, _, agent = _build(tmp_path, monkeypatch)
    gym.create_workout(
        workout_date=date(2026, 6, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    gym.tag_exercise("Bench Press", "chest")

    fake = _FakeChatClient(
        [
            OllamaChatResult(
                content=None,
                tool_calls=[OllamaToolCall(name="get_strength_score", arguments={})],
            ),
            OllamaChatResult(content="You're at 100% of your all-time peak.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake)

    result = asyncio.run(agent.ask([{"role": "user", "content": "how strong am I?"}]))

    assert result.answer == "You're at 100% of your all-time peak."
    assert result.tools_used == ["get_strength_score"]
    # The tool's real result (not a fabricated one) was fed back as context.
    second_call_messages = fake.calls[1]
    tool_messages = [item for item in second_call_messages if item.get("role") == "tool"]
    assert len(tool_messages) == 1
    payload = json.loads(tool_messages[0]["content"])
    assert payload["overall_score"] == 1.0


def test_dispatches_multiple_tool_calls_in_one_round(tmp_path: Path, monkeypatch) -> None:
    _, running, agent = _build(tmp_path, monkeypatch)
    running.create_run(
        run_date=date(2026, 6, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    fake = _FakeChatClient(
        [
            OllamaChatResult(
                content=None,
                tool_calls=[
                    OllamaToolCall(name="get_recent_runs", arguments={"limit": 1}),
                    OllamaToolCall(name="get_achievements", arguments={}),
                ],
            ),
            OllamaChatResult(content="Here's your recent activity.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake)

    result = asyncio.run(agent.ask([{"role": "user", "content": "what have I been up to?"}]))

    assert result.tools_used == ["get_recent_runs", "get_achievements"]
    tool_messages = [item for item in fake.calls[1] if item.get("role") == "tool"]
    assert len(tool_messages) == 2


def test_unknown_tool_name_is_reported_without_crashing(tmp_path: Path, monkeypatch) -> None:
    _, _, agent = _build(tmp_path, monkeypatch)
    fake = _FakeChatClient(
        [
            OllamaChatResult(
                content=None,
                tool_calls=[OllamaToolCall(name="get_the_weather", arguments={})],
            ),
            OllamaChatResult(content="I can't check that.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake)

    result = asyncio.run(agent.ask([{"role": "user", "content": "what's the weather?"}]))

    assert result.answer == "I can't check that."
    tool_messages = [item for item in fake.calls[1] if item.get("role") == "tool"]
    assert "error" in json.loads(tool_messages[0]["content"])


def test_falls_back_gracefully_when_ollama_becomes_unreachable_mid_loop(
    tmp_path: Path, monkeypatch
) -> None:
    _, _, agent = _build(tmp_path, monkeypatch)
    # First call succeeds, second call (after the tool result) fails open (None).
    fake = _FakeChatClient(
        [
            OllamaChatResult(
                content=None,
                tool_calls=[OllamaToolCall(name="get_strength_score", arguments={})],
            ),
        ]
    )
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake)

    result = asyncio.run(agent.ask([{"role": "user", "content": "how strong am I?"}]))

    assert result.available is False
    assert "reach Ollama" in result.answer
    assert result.tools_used == ["get_strength_score"]


def test_stops_after_max_iterations_if_ollama_never_settles(tmp_path: Path, monkeypatch) -> None:
    _, _, agent = _build(tmp_path, monkeypatch)
    always_wants_a_tool = OllamaChatResult(
        content=None, tool_calls=[OllamaToolCall(name="get_strength_score", arguments={})]
    )
    fake = _FakeChatClient([always_wants_a_tool] * 10)
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake)

    result = asyncio.run(agent.ask([{"role": "user", "content": "how strong am I?"}]))

    assert result.available is True
    assert "couldn't settle" in result.answer
    assert len(result.tools_used) == 5  # MAX_TOOL_ITERATIONS


def test_get_recent_runs_respects_limit(tmp_path: Path, monkeypatch) -> None:
    _, running, agent = _build(tmp_path, monkeypatch)
    for day in range(1, 5):
        running.create_run(
            run_date=date(2026, 6, day), run_type="outdoor", distance_km=5.0,
            average_pace_seconds_per_km=300, average_heart_rate=150,
        )

    runs = agent._get_recent_runs({"limit": 2})

    assert len(runs) == 2
    assert runs[0].run_date == date(2026, 6, 4)  # most recent first


def test_get_recent_workouts_includes_total_volume(tmp_path: Path, monkeypatch) -> None:
    gym, _, agent = _build(tmp_path, monkeypatch)
    gym.create_workout(
        workout_date=date(2026, 6, 1), name="Push", notes=None,
        sets=[
            {"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": "Overhead Press", "weight_kg": 40, "reps": 8, "rir": 2},
        ],
    )

    workouts = agent._get_recent_workouts({})

    assert len(workouts) == 1
    assert workouts[0]["total_volume_kg"] == 960.0
    assert len(workouts[0]["sets"]) == 2


class _FakeDockerMonitor:
    def collect(self, *, check_updates: bool = False) -> DockerSummary:
        return DockerSummary(
            available=True,
            total=2,
            running=1,
            stopped=1,
            unhealthy=0,
            updates_available=0,
            containers=[
                DockerContainer(
                    container_id="abc123",
                    name="sirisos-api",
                    image="sirisos-api:latest",
                    state="running",
                    status="Up 2 hours",
                    health="healthy",
                    cpu_percent=1.2,
                    memory_usage_bytes=100_000_000,
                    memory_limit_bytes=500_000_000,
                    memory_percent=20.0,
                ),
                DockerContainer(
                    container_id="def456",
                    name="sirisos-worker",
                    image="sirisos-worker:latest",
                    state="exited",
                    status="Exited (1) 3 hours ago",
                    health=None,
                    cpu_percent=None,
                    memory_usage_bytes=None,
                    memory_limit_bytes=None,
                    memory_percent=None,
                ),
            ],
        )


class _FakeHostMetricsCollector:
    def collect(self) -> HostMetrics:
        return HostMetrics(available=True, hostname="siris-server", cpu_percent=12.5, memory_percent=44.0)


class _FakeHomelabAlertService:
    def get_summary(self) -> HomelabAlertSummary:
        return HomelabAlertSummary(
            status="critical",
            warning_count=1,
            critical_count=1,
            alerts=[
                HomelabAlert(
                    id="docker-unavailable", severity="critical", source="Docker",
                    title="Docker monitoring unavailable", message="The Docker socket proxy cannot be reached.",
                ),
                HomelabAlert(
                    id="host-cpu", severity="warning", source="Host", title="High CPU usage",
                    message="CPU is at 85.0%, above the warning threshold of 80%.", value=85.0, threshold=80.0,
                ),
            ],
        )


def _build_with_homelab(tmp_path: Path, monkeypatch) -> SirisAgentService:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/siris_agent_homelab.db")
    return SirisAgentService(
        docker_monitor=_FakeDockerMonitor(),
        host_metrics_collector=_FakeHostMetricsCollector(),
        homelab_alert_service=_FakeHomelabAlertService(),
    )


def test_get_docker_status_returns_real_container_data(tmp_path: Path, monkeypatch) -> None:
    agent = _build_with_homelab(tmp_path, monkeypatch)

    status = agent._get_docker_status({})

    assert status.running == 1
    assert status.stopped == 1
    assert status.containers[0].name == "sirisos-api"
    assert status.containers[1].state == "exited"


def test_get_host_metrics_returns_real_data(tmp_path: Path, monkeypatch) -> None:
    agent = _build_with_homelab(tmp_path, monkeypatch)

    metrics = agent._get_host_metrics({})

    assert metrics.available is True
    assert metrics.cpu_percent == 12.5
    assert metrics.memory_percent == 44.0


def test_agent_dispatches_docker_status_through_the_full_loop(tmp_path: Path, monkeypatch) -> None:
    agent = _build_with_homelab(tmp_path, monkeypatch)
    fake_chat = _FakeChatClient(
        [
            OllamaChatResult(
                content=None,
                tool_calls=[OllamaToolCall(name="get_docker_status", arguments={})],
            ),
            OllamaChatResult(content="One container is down.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake_chat)

    result = asyncio.run(agent.ask([{"role": "user", "content": "Are all my containers healthy?"}]))

    assert result.tools_used == ["get_docker_status"]
    tool_messages = [item for item in fake_chat.calls[1] if item.get("role") == "tool"]
    payload = json.loads(tool_messages[0]["content"])
    assert payload["running"] == 1
    assert payload["containers"][1]["name"] == "sirisos-worker"


def test_get_homelab_alerts_returns_real_summary_data(tmp_path: Path, monkeypatch) -> None:
    agent = _build_with_homelab(tmp_path, monkeypatch)

    summary = agent._get_homelab_alerts({})

    assert summary.status == "critical"
    assert summary.warning_count == 1
    assert summary.critical_count == 1
    assert len(summary.alerts) == 2


def test_agent_dispatches_homelab_alerts_through_the_full_loop(tmp_path: Path, monkeypatch) -> None:
    agent = _build_with_homelab(tmp_path, monkeypatch)
    fake_chat = _FakeChatClient(
        [
            OllamaChatResult(
                content=None,
                tool_calls=[OllamaToolCall(name="get_homelab_alerts", arguments={})],
            ),
            OllamaChatResult(content="One critical and one warning alert are active.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake_chat)

    result = asyncio.run(agent.ask([{"role": "user", "content": "Any homelab alerts right now?"}]))

    assert result.tools_used == ["get_homelab_alerts"]
    tool_messages = [item for item in fake_chat.calls[1] if item.get("role") == "tool"]
    payload = json.loads(tool_messages[0]["content"])
    assert payload["status"] == "critical"
    assert payload["critical_count"] == 1
    assert payload["alerts"][0]["id"] == "docker-unavailable"


class _FakeReadinessService:
    def today(self):
        return DailyReadinessPoint(day=date(2026, 3, 10), score=78, hrv_ratio=85.0, sleep_ratio=71.0)


def _build_with_readiness(tmp_path: Path, monkeypatch) -> SirisAgentService:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/siris_agent_readiness.db")
    return SirisAgentService(readiness_service=_FakeReadinessService())


def test_get_readiness_score_returns_real_data(tmp_path: Path, monkeypatch) -> None:
    agent = _build_with_readiness(tmp_path, monkeypatch)

    point = agent._get_readiness_score({})

    assert point.score == 78
    assert point.hrv_ratio == 85.0
    assert point.sleep_ratio == 71.0


def test_agent_dispatches_readiness_score_through_the_full_loop(tmp_path: Path, monkeypatch) -> None:
    agent = _build_with_readiness(tmp_path, monkeypatch)
    fake_chat = _FakeChatClient(
        [
            OllamaChatResult(
                content=None,
                tool_calls=[OllamaToolCall(name="get_readiness_score", arguments={})],
            ),
            OllamaChatResult(content="Your readiness is 78 today, a bit below your norm.", tool_calls=[]),
        ]
    )
    monkeypatch.setattr("app.services.siris_agent_service.chat_client", fake_chat)

    result = asyncio.run(agent.ask([{"role": "user", "content": "How ready am I today?"}]))

    assert result.tools_used == ["get_readiness_score"]
    tool_messages = [item for item in fake_chat.calls[1] if item.get("role") == "tool"]
    payload = json.loads(tool_messages[0]["content"])
    assert payload["score"] == 78
    assert payload["hrv_ratio"] == 85.0
