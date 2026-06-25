import os
import httpx
from .source import MarketDataSource

BASE_URL = "https://api.massive.com"


class MassiveSource(MarketDataSource):
    """Market data source backed by the Massive (formerly Polygon.io) REST API."""

    interval_seconds = 15.0  # free tier: 5 req/min; one multi-ticker call per cycle

    def __init__(self, cache, get_tickers) -> None:
        super().__init__(cache, get_tickers)
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {os.environ['MASSIVE_API_KEY']}"},
            timeout=10.0,
        )

    async def fetch(self, tickers: set[str]) -> dict[str, float]:
        resp = await self._client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": ",".join(sorted(tickers))},
        )
        resp.raise_for_status()
        return {
            s["ticker"]: price
            for s in resp.json().get("tickers", [])
            if (price := _pick_price(s)) is not None
        }

    async def stop(self) -> None:
        await super().stop()
        await self._client.aclose()


def _pick_price(snap: dict) -> float | None:
    """Most real-time price available, with fallbacks for delayed plans."""
    for section, key in (("lastTrade", "p"), ("min", "c"), ("day", "c"), ("prevDay", "c")):
        value = (snap.get(section) or {}).get(key)
        if value:
            return float(value)
    return None
