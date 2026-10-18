from __future__ import annotations

from importlib import import_module


def test_flow_migration_creates_tables_and_expands_operation_datasets(monkeypatch):
    migration = import_module(
        "migrations.versions.0032_instrument_flow_observations"
    )
    created: list[str] = []
    checks: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        migration.op, "create_table", lambda name, *args, **kwargs: created.append(name)
    )
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition: checks.append((name, table, condition)),
    )

    migration.upgrade()

    assert created == ["instrument_flow_observations", "instrument_flow_coverages"]
    assert len(checks) == 2
    assert all("foreign_flow" in condition for _, _, condition in checks)


def test_flow_migration_downgrade_removes_tables_and_restores_dataset_constraints(
    monkeypatch,
):
    migration = import_module(
        "migrations.versions.0032_instrument_flow_observations"
    )
    dropped: list[str] = []
    checks: list[tuple[str, str, str]] = []
    monkeypatch.setattr(migration.op, "drop_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op, "drop_table", lambda name: dropped.append(name)
    )
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition: checks.append((name, table, condition)),
    )

    migration.downgrade()

    assert dropped == ["instrument_flow_coverages", "instrument_flow_observations"]
    assert len(checks) == 2
    assert all("foreign_flow" not in condition for _, _, condition in checks)
