from .source import MarketDataSource
from .sim_engine import GbmEngine


class SimulatorSource(MarketDataSource):
    """Market data source backed by the GBM simulator — no external dependencies."""

    interval_seconds = 0.5  # smooth, real-time-feeling motion

    def __init__(self, cache, get_tickers) -> None:
        super().__init__(cache, get_tickers)
        self._engine = GbmEngine()

    async def fetch(self, tickers: set[str]) -> dict[str, float]:
        return self._engine.step(tickers)  # synchronous GBM step; no I/O
