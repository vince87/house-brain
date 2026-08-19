from pathlib import Path

from house_brain.database import SQLITE_BUSY_TIMEOUT_MS, connect_database


def test_shared_database_uses_concurrency_safe_settings(tmp_path: Path) -> None:
    database = tmp_path / "house_brain.db"

    with connect_database(database) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout == SQLITE_BUSY_TIMEOUT_MS
    assert synchronous == 1


def test_wal_mode_persists_across_connections(tmp_path: Path) -> None:
    database = tmp_path / "house_brain.db"

    with connect_database(database) as first:
        first.execute("CREATE TABLE example (value TEXT NOT NULL)")
        first.execute("INSERT INTO example VALUES ('persisted')")

    with connect_database(database) as second:
        value = second.execute("SELECT value FROM example").fetchone()[0]
        journal_mode = second.execute("PRAGMA journal_mode").fetchone()[0]

    assert value == "persisted"
    assert journal_mode == "wal"
