"""scripts/reset-password.sh: sets the sign-in password in .env safely, against a stub docker."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "reset-password.sh"
ENV = (
    "SIRISOS_PORT=8094\n"
    "SIRISOS_ADMIN_USERNAME=brad\n"
    "SIRISOS_ADMIN_PASSWORD=old-Pass1!\n"
    "SIRISOS_JWT_SECRET=old-jwt-secret\n"
    "SIRISAI_API_KEY=keep-me\n"
)


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    script = tmp_path / "scripts" / "reset-password.sh"
    script.write_text(SCRIPT.read_text())
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    (tmp_path / ".env").write_text(ENV)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text('#!/bin/sh\necho "$@" >> "$(dirname "$0")/../docker.calls"\n')
    docker.chmod(0o755)
    return tmp_path


def run(folder: Path, typed: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{folder / 'bin'}:{os.environ['PATH']}"}
    return subprocess.run(["bash", str(folder / "scripts" / "reset-password.sh"), *args], input=typed, text=True,
                          capture_output=True, env=env)


def env_lines(folder: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in (folder / ".env").read_text().splitlines())


def test_sets_the_password_keeps_everything_else_and_recreates_the_container(folder):
    result = run(folder, "New-Pass%99x\nNew-Pass%99x\n")
    assert result.returncode == 0, result.stderr
    env = env_lines(folder)
    assert env["SIRISOS_ADMIN_PASSWORD"] == "New-Pass%99x"
    assert env["SIRISOS_JWT_SECRET"] == "old-jwt-secret"  # sessions stay signed in
    assert env["SIRISAI_API_KEY"] == "keep-me" and env["SIRISOS_ADMIN_USERNAME"] == "brad"
    assert (folder / "docker.calls").read_text().strip() == "compose up -d sirisos"
    assert "New-Pass%99x" not in result.stdout + result.stderr  # never printed
    assert "Sign in as brad" in result.stdout
    backup = next(folder.glob(".env.bak.*"))
    assert "SIRISOS_ADMIN_PASSWORD=old-Pass1!" in backup.read_text()
    assert stat.S_IMODE((folder / ".env").stat().st_mode) == 0o600


def test_sign_out_all_replaces_the_jwt_secret(folder):
    assert run(folder, "Another-Pass-77\nAnother-Pass-77\n", "--sign-out-all").returncode == 0
    secret = env_lines(folder)["SIRISOS_JWT_SECRET"]
    assert secret != "old-jwt-secret" and len(secret) == 96


def test_adds_the_line_when_there_was_none(folder):
    (folder / ".env").write_text("SIRISOS_ADMIN_USERNAME=brad\n")
    assert run(folder, "Fresh-Pass-123\nFresh-Pass-123\n").returncode == 0
    assert env_lines(folder)["SIRISOS_ADMIN_PASSWORD"] == "Fresh-Pass-123"


@pytest.mark.parametrize("typed, message", [
    ("Longenough1\nDifferent-One2\n", "don't match"),
    ("short\nshort\n", "at least 8"),
    ("has space here\nhas space here\n", "Avoid spaces"),
    ("dollar$ign-pass\ndollar$ign-pass\n", "Avoid spaces"),
])
def test_refuses_bad_passwords_and_changes_nothing(folder, typed, message):
    result = run(folder, typed)
    assert result.returncode == 1 and message in result.stderr
    assert (folder / ".env").read_text() == ENV
    assert not (folder / "docker.calls").exists() and not list(folder.glob(".env.bak.*"))


def test_needs_an_env_file(folder):
    (folder / ".env").unlink()
    assert "No .env here" in run(folder, "Longenough1\nLongenough1\n").stderr
