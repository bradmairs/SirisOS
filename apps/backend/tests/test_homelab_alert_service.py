from app.services.docker_service import DockerContainer, DockerSummary
from app.services.homelab_alert_service import HomelabAlertService
from app.services.host_metrics_service import HostMetrics


class _FakeHostMetricsCollector:
    def __init__(self, metrics: HostMetrics) -> None:
        self._metrics = metrics

    def collect(self) -> HostMetrics:
        return self._metrics


class _FakeDockerMonitor:
    def __init__(self, summary: DockerSummary) -> None:
        self._summary = summary

    def collect(self, *, check_updates: bool = False) -> DockerSummary:
        return self._summary


def _healthy_host() -> HostMetrics:
    return HostMetrics(available=True, hostname="siris-server", cpu_percent=10.0, memory_percent=20.0, disk_percent=30.0)


def _healthy_docker() -> DockerSummary:
    return DockerSummary(
        available=True, total=1, running=1, stopped=0, unhealthy=0, updates_available=0,
        containers=[
            DockerContainer(
                container_id="abc", name="sirisos-api", image="sirisos-api:latest",
                state="running", status="Up 1 hour", health="healthy",
                cpu_percent=1.0, memory_usage_bytes=1000, memory_limit_bytes=2000, memory_percent=50.0,
            )
        ],
    )


def test_healthy_when_nothing_is_wrong() -> None:
    service = HomelabAlertService(
        host_metrics_collector=_FakeHostMetricsCollector(_healthy_host()),
        docker_monitor=_FakeDockerMonitor(_healthy_docker()),
    )

    summary = service.get_summary()

    assert summary.status == "healthy"
    assert summary.warning_count == 0
    assert summary.critical_count == 0
    assert summary.alerts == []


def test_high_cpu_produces_a_warning_or_critical_alert() -> None:
    warning_host = HostMetrics(available=True, cpu_percent=85.0, memory_percent=20.0, disk_percent=30.0)
    service = HomelabAlertService(
        host_metrics_collector=_FakeHostMetricsCollector(warning_host),
        docker_monitor=_FakeDockerMonitor(_healthy_docker()),
    )

    summary = service.get_summary()

    assert summary.status == "warning"
    assert summary.warning_count == 1
    cpu_alert = summary.alerts[0]
    assert cpu_alert.source == "Host"
    assert cpu_alert.severity == "warning"
    assert cpu_alert.value == 85.0

    critical_host = HostMetrics(available=True, cpu_percent=99.0, memory_percent=20.0, disk_percent=30.0)
    service = HomelabAlertService(
        host_metrics_collector=_FakeHostMetricsCollector(critical_host),
        docker_monitor=_FakeDockerMonitor(_healthy_docker()),
    )

    summary = service.get_summary()

    assert summary.status == "critical"
    assert summary.critical_count == 1


def test_host_metrics_unavailable_produces_no_host_alerts() -> None:
    service = HomelabAlertService(
        host_metrics_collector=_FakeHostMetricsCollector(HostMetrics(available=False, error="unreachable")),
        docker_monitor=_FakeDockerMonitor(_healthy_docker()),
    )

    summary = service.get_summary()

    assert summary.status == "healthy"
    assert summary.alerts == []


def test_docker_unavailable_produces_a_critical_alert() -> None:
    service = HomelabAlertService(
        host_metrics_collector=_FakeHostMetricsCollector(_healthy_host()),
        docker_monitor=_FakeDockerMonitor(
            DockerSummary(
                available=False, total=0, running=0, stopped=0, unhealthy=0, updates_available=0,
                containers=[], error="Docker socket not reachable",
            )
        ),
    )

    summary = service.get_summary()

    assert summary.status == "critical"
    assert summary.critical_count == 1
    assert summary.alerts[0].id == "docker-unavailable"
    assert summary.alerts[0].message == "Docker socket not reachable"


def test_unhealthy_stopped_and_update_available_containers_each_produce_an_alert() -> None:
    docker = DockerSummary(
        available=True, total=3, running=1, stopped=1, unhealthy=1, updates_available=1,
        containers=[
            DockerContainer(
                container_id="unhealthy1", name="flaky-service", image="flaky:latest",
                state="running", status="Up 1 hour", health="unhealthy",
                cpu_percent=None, memory_usage_bytes=None, memory_limit_bytes=None, memory_percent=None,
            ),
            DockerContainer(
                container_id="stopped1", name="crashed-service", image="crashed:latest",
                state="exited", status="Exited (1)", health=None,
                cpu_percent=None, memory_usage_bytes=None, memory_limit_bytes=None, memory_percent=None,
            ),
            DockerContainer(
                container_id="stale1", name="stale-service", image="stale:latest",
                state="running", status="Up 1 hour", health="healthy",
                cpu_percent=None, memory_usage_bytes=None, memory_limit_bytes=None, memory_percent=None,
                update_available=True,
            ),
        ],
    )
    service = HomelabAlertService(
        host_metrics_collector=_FakeHostMetricsCollector(_healthy_host()),
        docker_monitor=_FakeDockerMonitor(docker),
    )

    summary = service.get_summary()

    assert summary.status == "critical"
    assert summary.critical_count == 1
    assert summary.warning_count == 2
    alert_ids = {alert.id for alert in summary.alerts}
    assert alert_ids == {
        "container-unhealthy1-unhealthy",
        "container-stopped1-stopped",
        "container-stale1-update",
    }
