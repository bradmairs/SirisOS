"""VERSION is the one source of truth; the API and the web app must match it
(scripts/bump-version.sh writes all three)."""

import re
from pathlib import Path

from app.main import API_VERSION

ROOT = Path(__file__).resolve().parents[3]


def test_api_and_web_versions_match_the_version_file() -> None:
    version = (ROOT / "VERSION").read_text().strip()
    assert re.fullmatch(r"\d+\.\d{1,2}", version), version
    web = (ROOT / "apps/web/src/version.ts").read_text()
    assert API_VERSION == version
    assert f'APP_VERSION = "{version}"' in web
    assert (ROOT / "docs/releases" / f"{version}.md").exists(), "write the release notes for this version"
