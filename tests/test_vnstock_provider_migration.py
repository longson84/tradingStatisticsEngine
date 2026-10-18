from __future__ import annotations

from importlib import import_module


def test_upgrade_migrates_only_active_exact_provider_identity(monkeypatch):
    migration = import_module(
        "migrations.versions.0031_migrate_vnstock_provider_identity"
    )
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    sql = " ".join(statements).lower()
    assert "update instrument_symbols" in sql
    assert "valid_to is null" in sql
    assert "namespace = 'vnstock_data'" in sql
    assert "source = 'vnstock_data'" in sql
    assert "provider_source" not in sql
    assert "fundamental" not in sql


def test_downgrade_reverses_only_active_exact_provider_identity(monkeypatch):
    migration = import_module(
        "migrations.versions.0031_migrate_vnstock_provider_identity"
    )
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.downgrade()

    sql = " ".join(statements).lower()
    assert "update instrument_symbols" in sql
    assert "valid_to is null" in sql
    assert "namespace = 'vnstock'" in sql
    assert "source = 'vnstock'" in sql
    assert "provider_source" not in sql
    assert "fundamental" not in sql
