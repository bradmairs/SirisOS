"""Apps SirisOS complements but doesn't talk to (no reachable server API):
tiles that just launch them. *_URL may be an app URL scheme."""

from __future__ import annotations

from app.hub.connectors.base import Connector


class LaunchConnector(Connector):
    launch_only = True
    category = "life"

    def missing_config(self) -> str:
        return f"Set {self.env_prefix}_URL in .env to add a launch link."


class HelmarrConnector(LaunchConnector):
    id, name, icon, env_prefix = "helmarr", "Helmarr", "film", "HELMARR"
    description = "Media: Sonarr, Radarr and friends."


class JefitConnector(LaunchConnector):
    id, name, icon, env_prefix = "jefit", "JEFIT", "dumbbell", "JEFIT"
    description = "Gym logging and training history."


class NeoServerConnector(LaunchConnector):
    id, name, icon, env_prefix = "neo-server", "Neo Server", "server", "NEO_SERVER"
    description = "Homelab monitoring and remote control."
