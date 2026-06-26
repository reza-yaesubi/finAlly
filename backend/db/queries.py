"""All database query functions for the FinAlly backend."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from db.connection import get_db_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Users / cash


def get_cash(user_id: str = "default") -> float:
    """Return cash balance for user."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"User not found: {user_id}")
    return row["cash_balance"]


def update_cash(new_balance: float, user_id: str = "default") -> None:
    """Set cash balance for user."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_balance, user_id),
        )


# ---------------------------------------------------------------------------
# Watchlist


def get_watchlist(user_id: str = "default") -> list[str]:
    """Return list of ticker strings for user's watchlist."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        ).fetchall()
    return [row["ticker"] for row in rows]


def add_to_watchlist(ticker: str, user_id: str = "default") -> None:
    """Add ticker to watchlist. Raises ValueError if already present."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, ticker.upper(), _now()),
            )
    except sqlite3.IntegrityError:
        raise ValueError("already exists")


def remove_from_watchlist(ticker: str, user_id: str = "default") -> None:
    """Remove ticker from watchlist."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )


# ---------------------------------------------------------------------------
# Positions


def get_positions(user_id: str = "default") -> list[dict]:
    """Return list of position dicts: {ticker, quantity, avg_cost, updated_at}."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_position(
    ticker: str, quantity: float, avg_cost: float, user_id: str = "default"
) -> None:
    """Insert or update a position row."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, ticker) DO UPDATE SET
                quantity = excluded.quantity,
                avg_cost = excluded.avg_cost,
                updated_at = excluded.updated_at
            """,
            (str(uuid.uuid4()), user_id, ticker.upper(), quantity, avg_cost, _now()),
        )


# ---------------------------------------------------------------------------
# Trades


def record_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = "default",
) -> None:
    """Append a trade record."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker.upper(), side, quantity, price, _now()),
        )


def get_trades(user_id: str = "default") -> list[dict]:
    """Return all trades for user, oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ticker, side, quantity, price, executed_at FROM trades WHERE user_id = ? ORDER BY executed_at",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Portfolio snapshots


def record_snapshot(total_value: float, user_id: str = "default") -> None:
    """Record a portfolio value snapshot."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, total_value, _now()),
        )


def get_snapshots(user_id: str = "default") -> list[dict]:
    """Return all snapshots for user: [{total_value, recorded_at}, ...]."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Chat messages


def add_chat_message(
    role: str,
    content: str,
    actions: dict | None = None,
    user_id: str = "default",
) -> None:
    """Append a chat message. actions is serialized to JSON."""
    actions_json = json.dumps(actions) if actions is not None else None
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, role, content, actions_json, _now()),
        )


def get_chat_history(limit: int = 20, user_id: str = "default") -> list[dict]:
    """Return the most recent chat messages in chronological order: [{role, content, actions, created_at}, ...]."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, actions, created_at
            FROM (
                SELECT role, content, actions, created_at, rowid
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY rowid DESC
                LIMIT ?
            )
            ORDER BY rowid ASC
            """,
            (user_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        entry = dict(row)
        entry["actions"] = json.loads(entry["actions"]) if entry["actions"] else None
        result.append(entry)
    return result
