"""Database path resolution."""

import os


def get_db_path() -> str:
    """Return the SQLite database file path from env or default."""
    return os.environ.get("DB_PATH", "db/finally.db")
