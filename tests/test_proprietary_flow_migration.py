from __future__ import annotations

from importlib import import_module


def test_proprietary_flow_migration_expands_operation_dataset_checks(monkeypatch):
    migration = import_module(
        "migrations.versions.0033_proprietary_flow_operations"
    )
    checks: list[str] = []
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition: checks.append(condition),
    )

    migration.upgrade()

    assert len(checks) == 2
    assert all("foreign_flow" in condition for condition in checks)
    assert all("proprietary_flow" in condition for condition in checks)


def test_proprietary_flow_migration_downgrade_retains_foreign_flow(monkeypatch):
    migration = import_module(
        "migrations.versions.0033_proprietary_flow_operations"
    )
    checks: list[str] = []
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition: checks.append(condition),
    )

    migration.downgrade()

    assert all("foreign_flow" in condition for condition in checks)
    assert all("proprietary_flow" not in condition for condition in checks)
