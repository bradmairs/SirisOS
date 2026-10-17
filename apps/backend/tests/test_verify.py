"""make verify: the end-to-end check, against the fake apps."""

from __future__ import annotations

import argparse
import asyncio

import httpx

from app import verify
from app.entrypoint import app
from tests.test_career import EA_CSV
from tests.test_hub import apps  # noqa: F401 - the fixture


def _run(**kwargs):
    args = argparse.Namespace(ea=kwargs.get("ea"), push=False, api="http://sirisos")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://sirisos") as api:
            return await verify.run(args, api)

    return asyncio.run(go())


def test_verify_reports_each_part_and_fails_on_broken_ones(apps, tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))
    export = tmp_path / "ea.csv"
    export.write_text(EA_CSV, encoding="utf-8")
    results = {r.name: r for r in _run(ea=str(export))}

    assert results["App: SirisAI"].state == "ok"
    assert results["App: Engineering Reviewer"].state == "ok"
    assert results["SirisAI's key into SirisOS"].state == "skip"
    assert results["Phone notifications"].state == "skip"
    ea = results["Engineers Australia export"]
    assert ea.state in ("ok", "warn") and "activities" in ea.detail and "(not saved)" in ea.detail
    assert not (tmp_path / "career.json").exists()  # nothing was imported
    # Defaults in the test environment are flagged.
    assert results["Security: Sign-in secret is a default or too short"].state == "fail"
    text, ok = verify.report(list(results.values()))
    assert not ok and "broken" in text and "✓ App: SirisAI" in text


def test_service_key_check(apps, monkeypatch):
    monkeypatch.setenv("SIRISOS_SERVICE_KEY", "k" * 32)
    results = {r.name: r for r in _run()}
    assert results["SirisAI's key into SirisOS"].state == "ok"
