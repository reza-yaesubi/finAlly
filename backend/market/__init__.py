import os
from collections.abc import Callable
from .cache import PriceCache
from .source import MarketDataSource
from .massive import MassiveSource
from .simulator import SimulatorSource

__all__ = ["PriceCache", "MarketDataSource", "MassiveSource", "SimulatorSource", "create_source"]


def create_source(cache: PriceCache, get_tickers: Callable[[], set[str]]) -> MarketDataSource:
    """Massive when MASSIVE_API_KEY is set and non-empty, else the simulator."""
    if os.environ.get("MASSIVE_API_KEY", "").strip():
        return MassiveSource(cache, get_tickers)
    return SimulatorSource(cache, get_tickers)
