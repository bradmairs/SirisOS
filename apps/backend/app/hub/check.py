"""Check every hub connector from inside the container, against the real
apps, without going through the web UI:

    docker compose exec sirisos python -m app.hub.check

Exit status is 1 when any configured app is down or degraded, so it can
gate a deploy script.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Mapping

from app.hub.service import Hub

ICON = {"ok": "✓", "degraded": "!", "down": "✗", "unconfigured": "·"}


async def run(env: Mapping[str, str]) -> tuple[list[str], bool]:
    hub = Hub(env, timeout=8.0, ttl=0)
    apps = await hub.apps(fresh=True, with_widgets=True)
    lines, healthy = [], True
    for app in apps:
        status = app["status"]
        state = status["state"]
        if state in ("down", "degraded"):
            healthy = False
        extra = []
        if status.get("version"):
            extra.append(status["version"])
        if status.get("latency_ms") is not None and state != "unconfigured":
            extra.append(f"{status['latency_ms']} ms")
        widget = app.get("widget")
        if isinstance(widget, dict) and "error" in widget:
            extra.append(f"widget: {widget['error']}")
        elif widget:
            extra.append("widget ok")
        detail = status.get("detail") or ""
        lines.append(
            f"{ICON[state]} {app['name']:<22} {state:<12} {' · '.join(extra)}" + (f"\n    {detail}" if detail else "")
        )
    return lines, healthy


def main() -> int:
    lines, healthy = asyncio.run(run(os.environ))
    print("\n".join(lines))
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
