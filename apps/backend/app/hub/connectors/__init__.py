from __future__ import annotations

from typing import Mapping

from app.hub.connectors.archive import ArchiveConnector
from app.hub.connectors.base import Connector
from app.hub.connectors.reviewer import ReviewerConnector
from app.hub.connectors.sirisai import SecondBrainConnector, SirisAIConnector
from app.hub.connectors.sirisdrone import SirisDroneConnector
from app.hub.connectors.sirislearn import SirisLearnConnector

# Home-screen order.
CONNECTOR_TYPES: tuple[type[Connector], ...] = (
    SirisAIConnector,
    SecondBrainConnector,
    ReviewerConnector,
    ArchiveConnector,
    SirisDroneConnector,
    SirisLearnConnector,
)


def build_connectors(env: Mapping[str, str]) -> list[Connector]:
    return [kind(env) for kind in CONNECTOR_TYPES]
