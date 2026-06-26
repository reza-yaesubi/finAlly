"""Database layer for FinAlly. Public API."""

from db.init import init_db
from db.queries import (
    get_cash,
    update_cash,
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    get_positions,
    upsert_position,
    record_trade,
    get_trades,
    record_snapshot,
    get_snapshots,
    add_chat_message,
    get_chat_history,
)

__all__ = [
    "init_db",
    "get_cash",
    "update_cash",
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "get_positions",
    "upsert_position",
    "record_trade",
    "get_trades",
    "record_snapshot",
    "get_snapshots",
    "add_chat_message",
    "get_chat_history",
]
