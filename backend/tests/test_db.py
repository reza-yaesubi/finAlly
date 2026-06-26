"""Unit tests for the database layer."""

import os
import sqlite3
import pytest


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Point DB_PATH to a fresh temp file for each test."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_file)
    yield db_file


# Import after env is patched via autouse fixture — but since autouse runs
# before the test body, we import inside tests or use lazy imports here.
# Simpler: import at module level; the fixture patches the env before each call.

import db as db_module
from db import (
    init_db,
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


# ---------------------------------------------------------------------------
# init_db


def test_init_db_creates_tables():
    db_path = os.environ["DB_PATH"]
    init_db()
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    expected = {"users_profile", "watchlist", "positions", "trades", "portfolio_snapshots", "chat_messages"}
    assert expected.issubset(tables)


def test_init_db_seeds_user_profile():
    init_db()
    cash = get_cash()
    assert cash == 10000.0


def test_init_db_seeds_watchlist():
    init_db()
    tickers = get_watchlist()
    assert len(tickers) == 10
    assert "AAPL" in tickers
    assert "NFLX" in tickers


def test_init_db_is_idempotent():
    init_db()
    init_db()  # second call should not duplicate seed data
    tickers = get_watchlist()
    assert len(tickers) == 10


# ---------------------------------------------------------------------------
# Watchlist


def test_add_and_get_watchlist():
    init_db()
    add_to_watchlist("PYPL")
    tickers = get_watchlist()
    assert "PYPL" in tickers


def test_remove_from_watchlist():
    init_db()
    remove_from_watchlist("AAPL")
    tickers = get_watchlist()
    assert "AAPL" not in tickers


def test_add_duplicate_watchlist_raises():
    init_db()
    with pytest.raises(ValueError, match="already exists"):
        add_to_watchlist("AAPL")  # already seeded


def test_watchlist_ticker_uppercased():
    init_db()
    # Use a ticker not in the seed list; verify lowercase is stored as uppercase
    add_to_watchlist("pypl")
    tickers = get_watchlist()
    assert "PYPL" in tickers
    assert "pypl" not in tickers


# ---------------------------------------------------------------------------
# Cash


def test_update_and_get_cash():
    init_db()
    update_cash(7500.0)
    assert get_cash() == 7500.0


def test_update_cash_to_zero():
    init_db()
    update_cash(0.0)
    assert get_cash() == 0.0


# ---------------------------------------------------------------------------
# Positions


def test_upsert_position_creates():
    init_db()
    upsert_position("AAPL", 10.0, 190.0)
    positions = get_positions()
    assert len(positions) == 1
    p = positions[0]
    assert p["ticker"] == "AAPL"
    assert p["quantity"] == 10.0
    assert p["avg_cost"] == 190.0


def test_upsert_position_updates():
    init_db()
    upsert_position("AAPL", 10.0, 190.0)
    upsert_position("AAPL", 20.0, 195.0)
    positions = get_positions()
    assert len(positions) == 1
    assert positions[0]["quantity"] == 20.0
    assert positions[0]["avg_cost"] == 195.0


def test_upsert_multiple_positions():
    init_db()
    upsert_position("AAPL", 5.0, 190.0)
    upsert_position("GOOGL", 2.0, 175.0)
    tickers = {p["ticker"] for p in get_positions()}
    assert tickers == {"AAPL", "GOOGL"}


# ---------------------------------------------------------------------------
# Trades


def test_record_and_get_trades():
    init_db()
    record_trade("AAPL", "buy", 10.0, 190.0)
    trades = get_trades()
    assert len(trades) == 1
    t = trades[0]
    assert t["ticker"] == "AAPL"
    assert t["side"] == "buy"
    assert t["quantity"] == 10.0
    assert t["price"] == 190.0


def test_get_trades_empty():
    init_db()
    assert get_trades() == []


def test_record_multiple_trades():
    init_db()
    record_trade("AAPL", "buy", 5.0, 190.0)
    record_trade("AAPL", "sell", 2.0, 195.0)
    trades = get_trades()
    assert len(trades) == 2
    assert trades[0]["side"] == "buy"
    assert trades[1]["side"] == "sell"


# ---------------------------------------------------------------------------
# Portfolio snapshots


def test_record_and_get_snapshots():
    init_db()
    record_snapshot(10250.0)
    snaps = get_snapshots()
    assert len(snaps) == 1
    assert snaps[0]["total_value"] == 10250.0
    assert "recorded_at" in snaps[0]


def test_get_snapshots_empty():
    init_db()
    assert get_snapshots() == []


def test_multiple_snapshots_ordered():
    init_db()
    record_snapshot(10000.0)
    record_snapshot(10500.0)
    snaps = get_snapshots()
    assert len(snaps) == 2
    assert snaps[0]["total_value"] == 10000.0
    assert snaps[1]["total_value"] == 10500.0


# ---------------------------------------------------------------------------
# Chat messages


def test_add_and_get_chat_history():
    init_db()
    add_chat_message("user", "Buy 5 AAPL")
    add_chat_message("assistant", "Done — bought 5 AAPL.", {"trades": [], "watchlist_changes": []})
    history = get_chat_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["actions"] is None
    assert history[1]["role"] == "assistant"
    assert history[1]["actions"] == {"trades": [], "watchlist_changes": []}


def test_chat_history_limit():
    init_db()
    for i in range(25):
        add_chat_message("user", f"message {i}")
    history = get_chat_history(limit=20)
    assert len(history) == 20


def test_chat_history_empty():
    init_db()
    assert get_chat_history() == []


def test_chat_history_order():
    init_db()
    add_chat_message("user", "first")
    add_chat_message("assistant", "second")
    history = get_chat_history()
    assert history[0]["content"] == "first"
    assert history[1]["content"] == "second"
