from __future__ import annotations

import json
import io
from pathlib import Path
import subprocess

import pytest

from scripts import setup_vnstock_data


def test_status_checks_distribution_and_ignored_key_file(monkeypatch, tmp_path):
    key_dir = tmp_path / ".vnstock"
    key_dir.mkdir()
    (key_dir / "api_key.json").write_text(
        json.dumps({"api_key": "secret"}), encoding="utf-8"
    )
    monkeypatch.setattr(setup_vnstock_data.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        setup_vnstock_data.metadata, "version", lambda name: "3.2.7"
    )
    monkeypatch.setattr(setup_vnstock_data, "env_value", lambda name: None)

    status = setup_vnstock_data.sponsor_status(home=tmp_path)

    assert status.installed
    assert status.supported
    assert status.api_key_configured


def test_installer_command_targets_project_environment_without_logging_key():
    command = setup_vnstock_data.installer_command(
        Path("/tmp/installer.run"), "secret", Path("/project/.venv")
    )

    assert command == [
        "/tmp/installer.run",
        "--",
        "--non-interactive",
        "--api-key",
        "secret",
        "--venv-path",
        "/project/.venv",
        "--language",
        "en",
    ]


def test_installer_failure_does_not_expose_api_key(monkeypatch, tmp_path):
    venv = tmp_path / ".venv"
    venv.mkdir()
    monkeypatch.setattr(
        setup_vnstock_data, "urlopen", lambda *args, **kwargs: io.BytesIO(b"#!/bin/sh")
    )

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(2, args[0])

    monkeypatch.setattr(setup_vnstock_data.subprocess, "run", fail)

    with pytest.raises(RuntimeError, match="exit code 2") as error:
        setup_vnstock_data.install(api_key="very-secret", venv=venv)

    assert "very-secret" not in str(error.value)
