from __future__ import annotations

from api.config import load_env_file


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
