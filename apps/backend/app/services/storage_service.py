from dataclasses import dataclass
import os
import re
from urllib.request import urlopen


@dataclass(frozen=True)
class StorageVolume:
    mountpoint: str
    device: str
    filesystem: str
    size_bytes: int
    available_bytes: int
    used_bytes: int
    used_percent: float


@dataclass(frozen=True)
class StorageSnapshot:
    available: bool
    volumes: tuple[StorageVolume, ...]
    total_bytes: int
    used_bytes: int
    available_bytes: int
    highest_used_percent: float | None
    error: str | None = None


class StorageService:
    _ignored_filesystems = {
        "autofs",
        "binfmt_misc",
        "cgroup",
        "cgroup2",
        "configfs",
        "debugfs",
        "devpts",
        "devtmpfs",
        "fusectl",
        "hugetlbfs",
        "mqueue",
        "overlay",
        "proc",
        "pstore",
        "securityfs",
        "squashfs",
        "sysfs",
        "tmpfs",
        "tracefs",
    }

    def __init__(self) -> None:
        self._url = os.getenv("NODE_EXPORTER_URL", "http://node-exporter:9100/metrics")

    def snapshot(self) -> StorageSnapshot:
        try:
            with urlopen(self._url, timeout=4) as response:
                text = response.read().decode("utf-8")
            volumes = self._parse_volumes(text)
            total = sum(volume.size_bytes for volume in volumes)
            available = sum(volume.available_bytes for volume in volumes)
            used = sum(volume.used_bytes for volume in volumes)
            highest = max((volume.used_percent for volume in volumes), default=None)
            return StorageSnapshot(
                available=True,
                volumes=tuple(volumes),
                total_bytes=total,
                used_bytes=used,
                available_bytes=available,
                highest_used_percent=highest,
            )
        except Exception as exc:
            return StorageSnapshot(
                available=False,
                volumes=(),
                total_bytes=0,
                used_bytes=0,
                available_bytes=0,
                highest_used_percent=None,
                error=str(exc),
            )

    def _parse_volumes(self, text: str) -> list[StorageVolume]:
        sizes: dict[tuple[str, str, str], float] = {}
        available: dict[tuple[str, str, str], float] = {}
        pattern = re.compile(
            r'^node_filesystem_(size|avail)_bytes\{([^}]*)\}\s+([0-9.eE+-]+)$'
        )
        for line in text.splitlines():
            match = pattern.match(line)
            if not match:
                continue
            metric, labels, raw_value = match.groups()
            label_values = self._labels(labels)
            mountpoint = label_values.get("mountpoint")
            device = label_values.get("device", "unknown")
            filesystem = label_values.get("fstype", "unknown")
            if not mountpoint or filesystem in self._ignored_filesystems:
                continue
            if mountpoint.startswith(("/run", "/var/lib/docker/overlay2")):
                continue
            key = (mountpoint, device, filesystem)
            value = float(raw_value)
            if metric == "size":
                sizes[key] = value
            else:
                available[key] = value

        volumes: list[StorageVolume] = []
        for key, size in sizes.items():
            if size < 1_000_000_000:
                continue
            free = available.get(key)
            if free is None or size <= 0:
                continue
            mountpoint, device, filesystem = key
            used = max(0.0, size - free)
            volumes.append(
                StorageVolume(
                    mountpoint=mountpoint,
                    device=device,
                    filesystem=filesystem,
                    size_bytes=int(size),
                    available_bytes=int(free),
                    used_bytes=int(used),
                    used_percent=round((used / size) * 100, 1),
                )
            )
        volumes.sort(key=lambda item: item.used_percent, reverse=True)
        return volumes

    @staticmethod
    def _labels(raw: str) -> dict[str, str]:
        return {
            key: value
            for key, value in re.findall(r'(\w+)="((?:\\.|[^"])*)"', raw)
        }
