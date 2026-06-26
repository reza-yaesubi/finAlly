"""
API integration tests using FastAPI's TestClient.

Uses a temp SQLite DB and a frozen PriceCache with fixed prices.
The market simulator is patched out so prices never change between calls.
"""

import asyncio
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

os.environ["LLM_MOCK"] = "true"

from market.cache import PriceCache

_FIXED_PRICES = {
    "AAPL": 190.0, "GOOGL": 175.0, "MSFT": 420.0,
    "AMZN": 185.0, "TSLA": 250.0, "NVDA": 880.0,
    "META": 510.0, "JPM": 200.0, "V": 280.0, "NFLX": 630.0,
}


def _make_cache() -> PriceCache:
    """PriceCache seeded with fixed prices — update() never called again during tests."""
    c = PriceCache()
    for ticker, price in _FIXED_PRICES.items():
        c.update(ticker, price)
    return c


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Each test gets a clean database."""
    db_file = tmp_path / "test.db"
    os.environ["DB_PATH"] = str(db_file)
    import db
    db.init_db()
    yield
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def client(fresh_db):
    fixed_cache = _make_cache()

    # Patch both create_source (so no simulator runs) and the shared cache
    # used by the app's lifespan so portfolio/stream modules get our fixed prices.
    mock_source = AsyncMock()
    mock_source.start = AsyncMock()
    mock_source.stop = AsyncMock()

    with patch("app.create_source", return_value=mock_source), \
         patch("app.cache", fixed_cache):

        from app import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# --- Health ---

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Watchlist ---

def test_get_watchlist_returns_default_tickers(client):
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    tickers = [item["ticker"] for item in resp.json()]
    assert "AAPL" in tickers
    assert len(tickers) == 10


def test_add_ticker_to_watchlist(client):
    resp = client.post("/api/watchlist", json={"ticker": "tsla"})
    # TSLA is already seeded — expect 409
    assert resp.status_code == 409

    resp = client.post("/api/watchlist", json={"ticker": "PLTR"})
    assert resp.status_code == 201
    assert resp.json()["ticker"] == "PLTR"


def test_add_duplicate_ticker_returns_409(client):
    resp = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert resp.status_code == 409


def test_remove_ticker_from_watchlist(client):
    resp = client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204

    watchlist = [item["ticker"] for item in client.get("/api/watchlist").json()]
    assert "AAPL" not in watchlist


# --- Portfolio ---

def test_get_portfolio_returns_correct_structure(client):
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert "cash" in data
    assert "total_value" in data
    assert "positions" in data
    assert data["cash"] == pytest.approx(10000.0)
    assert data["total_value"] == pytest.approx(10000.0)
    assert data["positions"] == []


# --- Trade ---

def test_buy_shares_updates_cash_and_creates_position(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["ticker"] == "AAPL"
    price = data["price"]
    assert price > 0
    assert data["cash_remaining"] == pytest.approx(10000.0 - 10 * price)

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash"] == pytest.approx(10000.0 - 10 * price)
    assert len(portfolio["positions"]) == 1
    assert portfolio["positions"][0]["ticker"] == "AAPL"
    assert portfolio["positions"][0]["quantity"] == pytest.approx(10.0)


def test_buy_fails_with_insufficient_cash(client):
    # Try to buy 1000 shares of NVDA @ $880 = $880,000 > $10,000 cash
    resp = client.post("/api/portfolio/trade", json={"ticker": "NVDA", "quantity": 1000, "side": "buy"})
    assert resp.status_code == 400
    assert "Insufficient cash" in str(resp.json())


def test_sell_fails_without_position(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "sell"})
    assert resp.status_code == 400
    assert "Insufficient shares" in str(resp.json())


def test_sell_shares_updates_cash(client):
    # Buy first
    buy_resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    buy_price = buy_resp.json()["price"]
    cash_after_buy = client.get("/api/portfolio").json()["cash"]

    # Then sell 5
    sell_resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "sell"})
    assert sell_resp.status_code == 200
    assert sell_resp.json()["ok"] is True
    sell_price = sell_resp.json()["price"]

    cash_after_sell = client.get("/api/portfolio").json()["cash"]
    assert cash_after_sell == pytest.approx(cash_after_buy + 5 * sell_price)


def test_portfolio_history(client):
    # Initially empty
    resp = client.get("/api/portfolio/history")
    assert resp.status_code == 200
    # Make a trade to trigger a snapshot
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"})
    resp = client.get("/api/portfolio/history")
    snapshots = resp.json()
    assert len(snapshots) >= 1
    assert "total_value" in snapshots[0]
    assert "recorded_at" in snapshots[0]


# --- Chat (mocked) ---

def test_chat_returns_mock_response(client):
    resp = client.post("/api/chat", json={"message": "How is my portfolio?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "trades" in data
    assert "watchlist_changes" in data
    assert isinstance(data["trades"], list)
    assert isinstance(data["watchlist_changes"], list)
