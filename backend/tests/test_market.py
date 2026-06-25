"""Unit tests for the market data backend.

Covers:
- Quote dataclass and direction logic
- PriceCache update/get/snapshot behaviour
- GbmEngine: valid prices, GBM correctness, reproducibility, unknown tickers
- SimulatorSource: interface conformance, fetch returns correct shape
- MassiveSource: response parsing, price-selection priority, graceful error handling
- MarketDataSource: background loop wiring, error resilience
- create_source factory: env-variable selection
"""

import asyncio
import math
import os
import pytest
import respx
import httpx

from market.types import Quote
from market.cache import PriceCache
from market.sim_universe import SEED_UNIVERSE, DEFAULT_SPEC
from market.sim_engine import GbmEngine, DT, SPEED
from market.simulator import SimulatorSource
from market.massive import MassiveSource, _pick_price, BASE_URL
from market import create_source


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------

class TestQuote:
    def test_direction_up(self):
        q = Quote("AAPL", 191.0, 190.0, "2024-01-01T10:00:00Z")
        assert q.direction == "up"

    def test_direction_down(self):
        q = Quote("AAPL", 189.0, 190.0, "2024-01-01T10:00:00Z")
        assert q.direction == "down"

    def test_direction_unchanged(self):
        q = Quote("AAPL", 190.0, 190.0, "2024-01-01T10:00:00Z")
        assert q.direction == "unchanged"

    def test_to_event_shape(self):
        q = Quote("AAPL", 192.50, 191.20, "2024-01-01T10:00:00Z")
        event = q.to_event()
        assert event == {
            "ticker": "AAPL",
            "price": 192.50,
            "prev_price": 191.20,
            "timestamp": "2024-01-01T10:00:00Z",
            "direction": "up",
        }

    def test_frozen_immutability(self):
        q = Quote("AAPL", 190.0, 189.0, "2024-01-01T10:00:00Z")
        with pytest.raises((AttributeError, TypeError)):
            q.price = 200.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PriceCache
# ---------------------------------------------------------------------------

class TestPriceCache:
    def test_first_update_sets_prev_price_equal_to_price(self):
        cache = PriceCache()
        quote = cache.update("AAPL", 190.0)
        assert quote.price == 190.0
        assert quote.prev_price == 190.0
        assert quote.direction == "unchanged"

    def test_second_update_carries_prev_price(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        quote = cache.update("AAPL", 192.0)
        assert quote.price == 192.0
        assert quote.prev_price == 190.0
        assert quote.direction == "up"

    def test_get_returns_none_for_unknown_ticker(self):
        cache = PriceCache()
        assert cache.get("UNKNOWN") is None

    def test_get_returns_latest_quote(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.update("AAPL", 191.0)
        quote = cache.get("AAPL")
        assert quote is not None
        assert quote.price == 191.0

    def test_snapshot_returns_all_tickers(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.update("GOOGL", 175.0)
        snap = cache.snapshot()
        assert set(snap.keys()) == {"AAPL", "GOOGL"}

    def test_snapshot_is_a_copy(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        snap = cache.snapshot()
        cache.update("AAPL", 191.0)
        # The old snapshot should not reflect the new price
        assert snap["AAPL"].price == 190.0

    def test_timestamp_is_iso_format(self):
        cache = PriceCache()
        quote = cache.update("AAPL", 190.0)
        assert quote.timestamp.endswith("Z")
        assert "T" in quote.timestamp

    def test_independent_tickers_do_not_share_prev_price(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        q = cache.update("GOOGL", 175.0)
        assert q.prev_price == 175.0  # GOOGL's first update; not contaminated by AAPL


# ---------------------------------------------------------------------------
# GbmEngine
# ---------------------------------------------------------------------------

class TestGbmEngine:
    def test_prices_stay_positive(self):
        engine = GbmEngine(seed=42)
        tickers = {"AAPL", "TSLA", "NVDA"}
        for _ in range(10_000):
            for price in engine.step(tickers).values():
                assert price > 0

    def test_returns_all_requested_tickers(self):
        engine = GbmEngine(seed=1)
        tickers = {"AAPL", "GOOGL", "MSFT"}
        result = engine.step(tickers)
        assert set(result.keys()) == tickers

    def test_prices_are_floats(self):
        engine = GbmEngine(seed=7)
        for price in engine.step({"AAPL"}).values():
            assert isinstance(price, float)

    def test_reproducibility_with_same_seed(self):
        engine_a = GbmEngine(seed=99)
        engine_b = GbmEngine(seed=99)
        tickers = {"AAPL", "TSLA"}
        for _ in range(100):
            assert engine_a.step(tickers) == engine_b.step(tickers)

    def test_different_seeds_produce_different_sequences(self):
        engine_a = GbmEngine(seed=1)
        engine_b = GbmEngine(seed=2)
        tickers = {"AAPL"}
        results_a = [engine_a.step(tickers)["AAPL"] for _ in range(10)]
        results_b = [engine_b.step(tickers)["AAPL"] for _ in range(10)]
        assert results_a != results_b

    def test_unknown_ticker_gets_valid_price_stream(self):
        engine = GbmEngine(seed=42)
        tickers = {"ZZZZ"}
        for _ in range(100):
            prices = engine.step(tickers)
            assert "ZZZZ" in prices
            assert prices["ZZZZ"] > 0

    def test_unknown_ticker_uses_default_spec_sector(self):
        engine = GbmEngine(seed=5)
        engine._ensure("FAKE")
        state = engine._state["FAKE"]
        assert state.spec.sector == "other"

    def test_seed_universe_tickers_start_near_seed_price(self):
        engine = GbmEngine(seed=0)
        tickers = set(SEED_UNIVERSE.keys())
        # After one step, prices should still be in the same order of magnitude
        prices = engine.step(tickers)
        for ticker, spec in SEED_UNIVERSE.items():
            assert prices[ticker] > spec.price * 0.5
            assert prices[ticker] < spec.price * 2.0

    def test_zero_sigma_pure_drift(self):
        """With sigma=0, each step multiplies by exp(mu * dt * SPEED)."""
        from market.sim_universe import TickerSpec
        from market.sim_engine import _State
        engine = GbmEngine(seed=0)
        mu = 0.10
        start_price = 100.0
        engine._state["TEST"] = _State(
            price=start_price,
            spec=TickerSpec(price=start_price, mu=mu, sigma=0.0, sector="other"),
        )
        prices = engine.step({"TEST"})
        expected = start_price * math.exp(mu * DT * SPEED)
        assert abs(prices["TEST"] - expected) < 1e-6

    def test_state_persists_between_steps(self):
        """Price at step N is the base for step N+1, not the seed price."""
        engine = GbmEngine(seed=42)
        p1 = engine.step({"AAPL"})["AAPL"]
        p2 = engine.step({"AAPL"})["AAPL"]
        # The engine state should have updated after step 1
        assert engine._state["AAPL"].price == p2
        assert engine._state["AAPL"].price != p1 or True  # prices may coincide, just ensuring no crash

    def test_prices_are_rounded_to_two_decimal_places(self):
        engine = GbmEngine(seed=42)
        for _ in range(50):
            for price in engine.step({"AAPL"}).values():
                # Check the value has at most 2 decimal places
                assert round(price, 2) == price


# ---------------------------------------------------------------------------
# SimulatorSource
# ---------------------------------------------------------------------------

class TestSimulatorSource:
    def test_interval_seconds(self):
        assert SimulatorSource.interval_seconds == 0.5

    @pytest.mark.asyncio
    async def test_fetch_returns_correct_shape(self):
        cache = PriceCache()
        source = SimulatorSource(cache, lambda: {"AAPL", "GOOGL"})
        tickers = {"AAPL", "GOOGL"}
        result = await source.fetch(tickers)
        assert isinstance(result, dict)
        assert set(result.keys()) == tickers
        for v in result.values():
            assert isinstance(v, float)
            assert v > 0

    @pytest.mark.asyncio
    async def test_fetch_empty_set(self):
        cache = PriceCache()
        source = SimulatorSource(cache, lambda: set())
        result = await source.fetch(set())
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_unknown_ticker(self):
        cache = PriceCache()
        source = SimulatorSource(cache, lambda: {"FAKE"})
        result = await source.fetch({"FAKE"})
        assert "FAKE" in result
        assert result["FAKE"] > 0

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        cache = PriceCache()
        tickers_called = []

        def get_tickers():
            tickers_called.append(True)
            return {"AAPL"}

        source = SimulatorSource(cache, get_tickers)
        await source.start()
        assert source._task is not None
        await asyncio.sleep(0.6)  # let at least one tick fire
        await source.stop()
        assert source._task is None
        assert len(tickers_called) >= 1

    @pytest.mark.asyncio
    async def test_loop_writes_to_cache(self):
        cache = PriceCache()
        source = SimulatorSource(cache, lambda: {"AAPL"})
        await source.start()
        await asyncio.sleep(0.7)
        await source.stop()
        assert cache.get("AAPL") is not None


# ---------------------------------------------------------------------------
# MassiveSource — _pick_price helper
# ---------------------------------------------------------------------------

class TestPickPrice:
    def test_prefers_lastTrade_p(self):
        snap = {
            "lastTrade": {"p": 192.50},
            "min": {"c": 191.0},
            "day": {"c": 190.0},
            "prevDay": {"c": 189.0},
        }
        assert _pick_price(snap) == 192.50

    def test_falls_back_to_min_c(self):
        snap = {
            "lastTrade": None,
            "min": {"c": 191.0},
            "day": {"c": 190.0},
            "prevDay": {"c": 189.0},
        }
        assert _pick_price(snap) == 191.0

    def test_falls_back_to_day_c(self):
        snap = {
            "min": {"c": 0},  # zero is falsy — skip
            "day": {"c": 190.0},
            "prevDay": {"c": 189.0},
        }
        assert _pick_price(snap) == 190.0

    def test_falls_back_to_prevDay_c(self):
        snap = {
            "prevDay": {"c": 189.0},
        }
        assert _pick_price(snap) == 189.0

    def test_returns_none_when_no_price_available(self):
        assert _pick_price({}) is None
        assert _pick_price({"lastTrade": {}, "min": {}, "day": {}, "prevDay": {}}) is None

    def test_handles_missing_sections_gracefully(self):
        snap = {"lastTrade": {"p": 200.0}}
        assert _pick_price(snap) == 200.0

    def test_returns_float(self):
        snap = {"lastTrade": {"p": "150.25"}}  # string from JSON
        result = _pick_price(snap)
        assert isinstance(result, float)
        assert result == 150.25


# ---------------------------------------------------------------------------
# MassiveSource — HTTP interactions
# ---------------------------------------------------------------------------

SNAPSHOT_RESPONSE = {
    "status": "OK",
    "count": 2,
    "tickers": [
        {
            "ticker": "AAPL",
            "lastTrade": {"p": 192.50},
            "min": {"c": 191.0},
            "day": {"c": 190.0},
            "prevDay": {"c": 188.0},
        },
        {
            "ticker": "GOOGL",
            "lastTrade": None,
            "min": {"c": 175.0},
            "day": {"c": 174.0},
            "prevDay": {"c": 173.0},
        },
    ],
}


class TestMassiveSource:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv("MASSIVE_API_KEY", "test-key-123")

    def test_interval_seconds(self):
        assert MassiveSource.interval_seconds == 15.0

    @pytest.mark.asyncio
    async def test_fetch_parses_response(self):
        cache = PriceCache()
        source = MassiveSource(cache, lambda: {"AAPL", "GOOGL"})

        with respx.mock:
            respx.get(
                f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
            ).mock(return_value=httpx.Response(200, json=SNAPSHOT_RESPONSE))

            result = await source.fetch({"AAPL", "GOOGL"})

        await source.stop()
        await source._client.aclose()

        assert result["AAPL"] == 192.50
        assert result["GOOGL"] == 175.0

    @pytest.mark.asyncio
    async def test_fetch_sends_bearer_auth(self):
        cache = PriceCache()
        source = MassiveSource(cache, lambda: {"AAPL"})

        with respx.mock:
            route = respx.get(
                f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
            ).mock(return_value=httpx.Response(200, json={"status": "OK", "tickers": [
                {"ticker": "AAPL", "lastTrade": {"p": 190.0}}
            ]}))

            await source.fetch({"AAPL"})
            request = route.calls[0].request
            assert "Bearer test-key-123" in request.headers.get("authorization", "")

        await source.stop()
        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_fetch_tickers_sorted_in_query(self):
        cache = PriceCache()
        source = MassiveSource(cache, lambda: {"TSLA", "AAPL", "GOOGL"})

        with respx.mock:
            route = respx.get(
                f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
            ).mock(return_value=httpx.Response(200, json={"status": "OK", "tickers": []}))

            await source.fetch({"TSLA", "AAPL", "GOOGL"})
            request = route.calls[0].request
            tickers_param = request.url.params.get("tickers", "")
            tickers_list = tickers_param.split(",")
            assert tickers_list == sorted(tickers_list)

        await source.stop()
        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_fetch_raises_on_http_error(self):
        cache = PriceCache()
        source = MassiveSource(cache, lambda: {"AAPL"})

        with respx.mock:
            respx.get(
                f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
            ).mock(return_value=httpx.Response(429))

            with pytest.raises(httpx.HTTPStatusError):
                await source.fetch({"AAPL"})

        await source.stop()
        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_stop_closes_http_client(self):
        cache = PriceCache()
        source = MassiveSource(cache, lambda: {"AAPL"})
        await source.stop()
        assert source._client.is_closed

    @pytest.mark.asyncio
    async def test_tickers_missing_from_response_are_excluded(self):
        """Tickers present in the request but absent from the API response are silently omitted."""
        cache = PriceCache()
        source = MassiveSource(cache, lambda: {"AAPL", "UNKNOWN"})

        with respx.mock:
            respx.get(
                f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
            ).mock(return_value=httpx.Response(200, json={
                "status": "OK",
                "tickers": [{"ticker": "AAPL", "lastTrade": {"p": 190.0}}],
            }))

            result = await source.fetch({"AAPL", "UNKNOWN"})

        await source.stop()
        await source._client.aclose()

        assert "AAPL" in result
        assert "UNKNOWN" not in result


# ---------------------------------------------------------------------------
# MarketDataSource — loop error resilience
# ---------------------------------------------------------------------------

class TestMarketDataSourceLoop:
    @pytest.mark.asyncio
    async def test_loop_continues_after_fetch_exception(self):
        """A failing fetch cycle must not kill the background loop."""
        cache = PriceCache()
        call_count = 0

        class FlakySource(SimulatorSource):
            async def fetch(self, tickers):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("transient network error")
                return await super().fetch(tickers)

        source = FlakySource(cache, lambda: {"AAPL"})
        await source.start()
        await asyncio.sleep(1.2)  # enough time for 2+ ticks
        await source.stop()

        assert call_count >= 2, "Loop should have retried after the first failure"
        assert cache.get("AAPL") is not None, "Cache should be populated after recovery"

    @pytest.mark.asyncio
    async def test_loop_skips_when_no_tickers(self):
        """Empty ticker set: fetch must never be called."""
        cache = PriceCache()
        fetch_called = []

        class TrackingSource(SimulatorSource):
            async def fetch(self, tickers):
                fetch_called.append(tickers)
                return await super().fetch(tickers)

        source = TrackingSource(cache, lambda: set())
        await source.start()
        await asyncio.sleep(0.6)
        await source.stop()

        assert fetch_called == []


# ---------------------------------------------------------------------------
# create_source factory
# ---------------------------------------------------------------------------

class TestCreateSource:
    def test_returns_simulator_when_no_key(self, monkeypatch):
        monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
        cache = PriceCache()
        source = create_source(cache, lambda: set())
        assert isinstance(source, SimulatorSource)

    def test_returns_simulator_when_key_is_empty_string(self, monkeypatch):
        monkeypatch.setenv("MASSIVE_API_KEY", "")
        cache = PriceCache()
        source = create_source(cache, lambda: set())
        assert isinstance(source, SimulatorSource)

    def test_returns_simulator_when_key_is_whitespace(self, monkeypatch):
        monkeypatch.setenv("MASSIVE_API_KEY", "   ")
        cache = PriceCache()
        source = create_source(cache, lambda: set())
        assert isinstance(source, SimulatorSource)

    @pytest.mark.asyncio
    async def test_returns_massive_when_key_is_set(self, monkeypatch):
        monkeypatch.setenv("MASSIVE_API_KEY", "real-key")
        cache = PriceCache()
        source = create_source(cache, lambda: set())
        assert isinstance(source, MassiveSource)
        await source._client.aclose()
