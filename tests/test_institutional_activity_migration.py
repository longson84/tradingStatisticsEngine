from importlib import import_module

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_institutional_activity_migration_creates_and_removes_isolated_tables():
    migration = import_module("migrations.versions.0039_institutional_activity")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE instruments (id INTEGER PRIMARY KEY)")
        before = set(sa.inspect(connection).get_table_names())

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        inspector = sa.inspect(connection)
        expected = {
            "instrument_identifiers",
            "institutional_managers",
            "institutional_filings",
            "institutional_filing_positions",
        }
        assert set(inspector.get_table_names()) == before | expected
        position_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys(
            "institutional_filing_positions"
        )}
        assert position_fks == {"institutional_filings", "instruments"}
        checks = " ".join(
            item["sqltext"]
            for item in inspector.get_check_constraints("institutional_filing_positions")
        )
        assert "shares > 0" in checks
        assert "put_call" in checks

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert set(sa.inspect(connection).get_table_names()) == before
    engine.dispose()


def test_institutional_activity_migration_follows_current_head():
    migration = import_module("migrations.versions.0039_institutional_activity")
    assert migration.down_revision == "0038"
