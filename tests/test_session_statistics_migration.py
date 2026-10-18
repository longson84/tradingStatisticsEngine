from importlib import import_module


def test_session_statistics_migration_creates_and_removes_only_snapshot_tables(
    monkeypatch,
):
    migration = import_module(
        "migrations.versions.0034_instrument_session_statistics"
    )
    created: list[str] = []
    dropped: list[str] = []
    monkeypatch.setattr(
        migration.op, "create_table", lambda name, *args, **kwargs: created.append(name)
    )
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "drop_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op, "drop_table", lambda name: dropped.append(name)
    )

    migration.upgrade()
    migration.downgrade()

    assert created == [
        "instrument_session_stat_snapshots",
        "instrument_session_stat_metrics",
    ]
    assert dropped == [
        "instrument_session_stat_metrics",
        "instrument_session_stat_snapshots",
    ]
    assert "instrument_flow_observations" not in dropped
