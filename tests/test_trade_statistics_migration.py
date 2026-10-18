from importlib import import_module

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_trade_statistics_migration_upgrade_and_downgrade_are_isolated():
    migration = import_module("migrations.versions.0037_instrument_daily_trade_statistics")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        for name in (
            "instruments", "price_bars", "instrument_flow_observations",
            "instrument_session_stat_snapshots", "instrument_session_stat_metrics",
        ):
            connection.exec_driver_sql(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql(f"INSERT INTO {name} (id) VALUES (1)")
        before = set(sa.inspect(connection).get_table_names())
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        inspector = sa.inspect(connection)
        table = "instrument_daily_trade_statistics"
        assert set(inspector.get_table_names()) == before | {table}
        assert inspector.get_foreign_keys(table)[0]["options"]["ondelete"] == "CASCADE"
        assert inspector.get_unique_constraints(table)[0]["column_names"] == [
            "instrument_id", "trading_date",
        ]
        checks = " ".join(item["sqltext"] for item in inspector.get_check_constraints(table))
        assert "schema_version > 0" in checks
        for field in (
            "market_cap", "total_shares", "matched_volume", "matched_value",
            "deal_volume", "deal_value", "total_volume", "total_value",
            "total_buy_trade", "total_buy_trade_volume", "total_sell_trade",
            "total_sell_trade_volume", "total_buy_unmatched_volume",
            "total_sell_unmatched_volume", "average_buy_trade_volume",
            "average_sell_trade_volume",
        ):
            assert field in checks
        assert "total_net_trade_volume" not in checks
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert set(sa.inspect(connection).get_table_names()) == before
        for name in before:
            assert connection.exec_driver_sql(f"SELECT COUNT(*) FROM {name}").scalar() == 1
    engine.dispose()


def test_trade_statistics_migration_postgres_uses_fixed_point_provenance(monkeypatch):
    migration = import_module("migrations.versions.0037_instrument_daily_trade_statistics")
    tables = []
    monkeypatch.setattr(migration.op, "create_table", lambda name, *args: tables.append((name, args)))
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    migration.upgrade()
    columns = {item.name: item for item in tables[0][1] if isinstance(item, sa.Column)}
    fixed_point = [item for item in columns.values() if isinstance(item.type, sa.Numeric)]
    assert len(fixed_point) == 17
    assert all((item.type.precision, item.type.scale) == (38, 6) for item in fixed_point)
    assert columns["fetched_at"].type.timezone
    assert all(not columns[name].nullable for name in (
        "instrument_id", "trading_date", "source", "schema_version", "fetched_at",
    ))
    assert migration.down_revision == "0036"
