from dataclasses import dataclass
import os
import re
import time
from urllib.request import urlopen


@dataclass(frozen=True)
class HostMetrics:
    available: bool
    hostname: str | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    disk_percent: float | None = None
    disk_used_bytes: int | None = None
    disk_total_bytes: int | None = None
    load_1m: float | None = None
    uptime_seconds: float | None = None
    network_receive_bytes_per_second: float | None = None
    network_transmit_bytes_per_second: float | None = None
    error: str | None = None


class HostMetricsCollector:
    def __init__(self) -> None:
        self._url = os.getenv("NODE_EXPORTER_URL", "http://node-exporter:9100/metrics")
        self._previous_cpu: tuple[float, float] | None = None
        self._previous_network: tuple[float, float, float] | None = None

    def collect(self) -> HostMetrics:
        try:
            with urlopen(self._url, timeout=4) as response:
                text = response.read().decode("utf-8")

            metrics = self._parse_metrics(text)
            hostname = self._hostname(text)

            memory_total = metrics.get("node_memory_MemTotal_bytes")
            memory_available = metrics.get("node_memory_MemAvailable_bytes")
            memory_used = None
            memory_percent = None
            if memory_total and memory_available is not None:
                memory_used = int(memory_total - memory_available)
                memory_percent = round((memory_used / memory_total) * 100, 1)

            disk_total, disk_available = self._root_filesystem(text)
            disk_used = None
            disk_percent = None
            if disk_total and disk_available is not None:
                disk_used = int(disk_total - disk_available)
                disk_percent = round((disk_used / disk_total) * 100, 1)

            cpu_idle = self._sum_cpu(text, mode="idle")
            cpu_total = self._sum_cpu(text)
            cpu_percent = None
            if self._previous_cpu is not None:
                previous_idle, previous_total = self._previous_cpu
                total_delta = cpu_total - previous_total
                idle_delta = cpu_idle - previous_idle
                if total_delta > 0:
                    cpu_percent = round((1 - idle_delta / total_delta) * 100, 1)
            self._previous_cpu = (cpu_idle, cpu_total)

            received_total, transmitted_total = self._network_totals(text)
            now = time.monotonic()
            receive_rate = transmit_rate = None
            if self._previous_network is not None:
                previous_time, previous_received, previous_transmitted = self._previous_network
                elapsed = now - previous_time
                if elapsed > 0:
                    receive_rate = max(0.0, (received_total - previous_received) / elapsed)
                    transmit_rate = max(0.0, (transmitted_total - previous_transmitted) / elapsed)
            self._previous_network = (now, received_total, transmitted_total)

            return HostMetrics(
                available=True,
                hostname=hostname,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_bytes=memory_used,
                memory_total_bytes=int(memory_total) if memory_total else None,
                disk_percent=disk_percent,
                disk_used_bytes=disk_used,
                disk_total_bytes=int(disk_total) if disk_total else None,
                load_1m=metrics.get("node_load1"),
                uptime_seconds=metrics.get("node_time_seconds", 0) - metrics.get("node_boot_time_seconds", 0),
                network_receive_bytes_per_second=round(receive_rate, 1) if receive_rate is not None else None,
                network_transmit_bytes_per_second=round(transmit_rate, 1) if transmit_rate is not None else None,
            )
        except Exception as exc:
            return HostMetrics(available=False, error=str(exc))

    @staticmethod
    def _parse_metrics(text: str) -> dict[str, float]:
        values: dict[str, float] = {}
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            try:
                values[parts[0]] = float(parts[1])
            except ValueError:
                continue
        return values

    @staticmethod
    def _hostname(text: str) -> str | None:
        match = re.search(r'node_uname_info\{[^}]*nodename="([^"]+)"', text)
        return match.group(1) if match else None

    @staticmethod
    def _sum_cpu(text: str, mode: str | None = None) -> float:
        total = 0.0
        for match in re.finditer(r'node_cpu_seconds_total\{([^}]*)\}\s+([0-9.eE+-]+)', text):
            labels, value = match.groups()
            if mode is not None and f'mode="{mode}"' not in labels:
                continue
            total += float(value)
        return total

    @staticmethod
    def _root_filesystem(text: str) -> tuple[float | None, float | None]:
        size = avail = None
        for line in text.splitlines():
            if 'mountpoint="/"' not in line:
                continue
            if line.startswith("node_filesystem_size_bytes"):
                size = float(line.rsplit(" ", 1)[1])
            elif line.startswith("node_filesystem_avail_bytes"):
                avail = float(line.rsplit(" ", 1)[1])
        return size, avail

    @staticmethod
    def _network_totals(text: str) -> tuple[float, float]:
        received = transmitted = 0.0
        ignored = {'lo', 'docker0'}
        for match in re.finditer(r'node_network_(receive|transmit)_bytes_total\{([^}]*)\}\s+([0-9.eE+-]+)', text):
            direction, labels, value = match.groups()
            device_match = re.search(r'device="([^"]+)"', labels)
            device = device_match.group(1) if device_match else ''
            if device in ignored or device.startswith(('veth', 'br-', 'tun', 'tap')):
                continue
            if direction == 'receive':
                received += float(value)
            else:
                transmitted += float(value)
        return received, transmitted
