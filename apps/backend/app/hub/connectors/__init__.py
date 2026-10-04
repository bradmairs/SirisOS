from __future__ import annotations

from typing import Mapping

from app.hub.connectors.apd_pm import APDPMConnector
from app.hub.connectors.archive import ArchiveConnector
from app.hub.connectors.base import Connector
from app.hub.connectors.gvw import GVWConnector
from app.hub.connectors.launch import HelmarrConnector, JefitConnector, NeoServerConnector
from app.hub.connectors.reviewer import ReviewerConnector
from app.hub.connectors.sirisai import SecondBrainConnector, SirisAIConnector
from app.hub.connectors.sirisdrone import SirisDroneConnector

# Home-screen order.
CONNECTOR_TYPES: tuple[type[Connector], ...] = (
    SirisAIConnector,
    SecondBrainConnector,
    APDPMConnector,
    ReviewerConnector,
    ArchiveConnector,
    GVWConnector,
    SirisDroneConnector,
    JefitConnector,
    HelmarrConnector,
    NeoServerConnector,
)


def build_connectors(env: Mapping[str, str]) -> list[Connector]:
    return [kind(env) for kind in CONNECTOR_TYPES]
