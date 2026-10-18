from importlib import import_module


def test_session_statistics_operation_migration_changes_run_only(monkeypatch):
    migration = import_module(
        "migrations.versions.0035_session_statistics_operations"
    )
    dropped = []
    created = []
    added = []
    removed = []
    monkeypatch.setattr(
        migration.op, "drop_constraint",
        lambda name, table, **kwargs: dropped.append((name, table)),
    )
    monkeypatch.setattr(
        migration.op, "create_check_constraint",
        lambda name, table, condition: created.append((table, condition)),
    )
    monkeypatch.setattr(
        migration.op, "add_column", lambda table, column: added.append((table, column.name))
    )
    monkeypatch.setattr(
        migration.op, "drop_column", lambda table, column: removed.append((table, column))
    )

    migration.upgrade()
    migration.downgrade()

    assert all(table == "data_operation_runs" for _, table in dropped)
    assert any("session_stats" in condition for _, condition in created)
    assert any("proprietary_flow" in condition and "session_stats" not in condition for _, condition in created)
    assert added == [
        ("data_operation_runs", "period_start"),
        ("data_operation_runs", "period_end"),
    ]
    assert removed == [
        ("data_operation_runs", "period_end"),
        ("data_operation_runs", "period_start"),
    ]
