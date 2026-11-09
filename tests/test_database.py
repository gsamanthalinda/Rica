import pytest

from database import engine


def test_app_sqlite_connections_enforce_foreign_keys():
    if engine.dialect.name != "sqlite":
        pytest.skip("Only SQLite needs foreign keys switched on per connection")

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
