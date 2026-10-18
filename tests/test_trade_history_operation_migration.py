from importlib import import_module

import sqlalchemy as sa


def test_trade_history_migration_changes_only_single_run_dataset_constraint(monkeypatch):
    migration = import_module("migrations.versions.0038_trade_history_operations")
    calls = []
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: calls.append(("drop", args, kwargs)))
    monkeypatch.setattr(migration.op, "create_check_constraint", lambda *args, **kwargs: calls.append(("create", args, kwargs)))
    monkeypatch.setattr(migration.op, "execute", lambda statement: calls.append(("execute", str(statement))))
    for operation in ("add_column", "drop_column", "create_table", "drop_table", "create_index", "drop_index"):
        monkeypatch.setattr(migration.op, operation, lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected migration mutation")))
    assert migration.revision == "0038"
    assert migration.down_revision == "0037"
    migration.upgrade()
    migration.downgrade()
    assert calls == [
        ("drop", ("ck_data_operation_runs_dataset", "data_operation_runs"), {"type_": "check"}),
        ("create", ("ck_data_operation_runs_dataset", "data_operation_runs",
                    "dataset IN ('prices', 'fundamentals', 'foreign_flow', 'proprietary_flow', 'session_stats', 'trade_history')"), {}),
        ("execute", "DELETE FROM data_operation_runs WHERE dataset = 'trade_history'"),
        ("drop", ("ck_data_operation_runs_dataset", "data_operation_runs"), {"type_": "check"}),
        ("create", ("ck_data_operation_runs_dataset", "data_operation_runs",
                    "dataset IN ('prices', 'fundamentals', 'foreign_flow', 'proprietary_flow', 'session_stats')"), {}),
    ]


def test_trade_history_downgrade_removes_only_owned_runs_before_narrowing_check(monkeypatch):
    migration = import_module("migrations.versions.0038_trade_history_operations")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE data_operation_runs (id TEXT PRIMARY KEY, dataset TEXT NOT NULL)")
        connection.exec_driver_sql("INSERT INTO data_operation_runs VALUES ('activity', 'trade_history'), ('price', 'prices'), ('session', 'session_stats')")
        monkeypatch.setattr(migration.op, "execute", connection.execute)
        monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: None)

        def recreate_older_check(*args, **kwargs):
            # Observe real remaining rows at constraint creation, not SQL text alone.
            assert connection.exec_driver_sql(
                "SELECT id, dataset FROM data_operation_runs ORDER BY id"
            ).all() == [("price", "prices"), ("session", "session_stats")]

        monkeypatch.setattr(migration.op, "create_check_constraint", recreate_older_check)
        migration.downgrade()
    engine.dispose()
