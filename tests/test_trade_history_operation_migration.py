from importlib import import_module


def test_trade_history_migration_changes_only_single_run_dataset_constraint(monkeypatch):
    migration = import_module("migrations.versions.0038_trade_history_operations")
    calls = []
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: calls.append(("drop", args, kwargs)))
    monkeypatch.setattr(migration.op, "create_check_constraint", lambda *args, **kwargs: calls.append(("create", args, kwargs)))
    for operation in ("add_column", "drop_column", "create_table", "drop_table", "execute", "create_index", "drop_index"):
        monkeypatch.setattr(migration.op, operation, lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected migration mutation")))
    assert migration.revision == "0038"
    assert migration.down_revision == "0037"
    migration.upgrade()
    migration.downgrade()
    assert calls == [
        ("drop", ("ck_data_operation_runs_dataset", "data_operation_runs"), {"type_": "check"}),
        ("create", ("ck_data_operation_runs_dataset", "data_operation_runs",
                    "dataset IN ('prices', 'fundamentals', 'foreign_flow', 'proprietary_flow', 'session_stats', 'trade_history')"), {}),
        ("drop", ("ck_data_operation_runs_dataset", "data_operation_runs"), {"type_": "check"}),
        ("create", ("ck_data_operation_runs_dataset", "data_operation_runs",
                    "dataset IN ('prices', 'fundamentals', 'foreign_flow', 'proprietary_flow', 'session_stats')"), {}),
    ]
