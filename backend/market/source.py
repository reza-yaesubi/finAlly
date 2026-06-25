import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from .cache import PriceCache

log = logging.getLogger("market")


class MarketDataSource(ABC):
    """Background task that keeps the PriceCache fresh for the current ticker set."""

    interval_seconds: float  # set by subclass

    def __init__(self, cache: PriceCache, get_tickers: Callable[[], set[str]]) -> None:
        self._cache = cache
        self._get_tickers = get_tickers  # returns the live watchlist ∪ positions set
        self._task: asyncio.Task | None = None

    @abstractmethod
    async def fetch(self, tickers: set[str]) -> dict[str, float]:
        """Return latest prices for the given tickers."""

    async def _loop(self) -> None:
        while True:
            tickers = self._get_tickers()
            if tickers:
                try:
                    prices = await self.fetch(tickers)
                    for ticker, price in prices.items():
                        self._cache.update(ticker, price)
                except Exception:  # noqa: BLE001 - one bad cycle must not kill the loop
                    log.exception("market fetch cycle failed; retrying next interval")
            await asyncio.sleep(self.interval_seconds)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
