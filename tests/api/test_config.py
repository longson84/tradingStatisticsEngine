from __future__ import annotations

import pytest

from api.config import env_bool, env_float, load_env_file


def test_load_env_file_adds_missing_values_without_overriding(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local secrets\nFIRST=from-file\nSECOND='quoted value'\n",
        encoding="utf-8",
    )
    environ = {"FIRST": "already-set"}

    loaded = load_env_file(env_file, environ=environ)

    assert loaded == ("SECOND",)
    assert environ == {"FIRST": "already-set", "SECOND": "quoted value"}


def test_typed_env_values(monkeypatch):
    monkeypatch.setenv("FEATURE_ENABLED", "yes")
    monkeypatch.setenv("REQUEST_RATE", "120.5")

    assert env_bool("FEATURE_ENABLED") is True
    assert env_float("REQUEST_RATE", 1.0) == 120.5


def test_invalid_boolean_is_rejected(monkeypatch):
    monkeypatch.setenv("FEATURE_ENABLED", "sometimes")

    with pytest.raises(ValueError, match="must be a boolean"):
        env_bool("FEATURE_ENABLED")
