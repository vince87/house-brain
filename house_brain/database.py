import sqlite3
from pathlib import Path

SQLITE_BUSY_TIMEOUT_MS = 30_000


def connect_database(path: Path) -> sqlite3.Connection:
    """Open the shared persistent database with concurrency-safe defaults."""
    connection = sqlite3.connect(
        path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection
