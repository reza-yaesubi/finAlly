# Market Data Interface — Unified Price Source

The design of the single Python interface that supplies live prices to FinAlly,
selecting the **Massive API** when `MASSIVE_API_KEY` is set and the **built-in
simulator** otherwise. Everything downstream (SSE streaming, price cache,
frontend) is agnostic to which source is active.

Companion docs: `MASSIVE_API.md` (real data), `MARKET_SIMULATOR.md` (sim data).

---

## 1. Design Goals

- **One interface, two implementations.** Simulator and Massive poller conform
  to the same small abstract base.
- **One shared price cache.** A single background task writes the latest price
  per ticker into an in-memory cache; SSE reads from it. (Per `PLAN.md` §6.)
- **Source selected once, at startup**, from the environment.
- **Dynamic ticker set.** The watched set = union of watchlist tickers and held
  position tickers, and it changes at runtime (add/remove watchlist). The source
  reads the current set on each cycle rather than capturing it once.
- **No defensive overengineering.** A failed Massive request logs and is skipped;
  the next cycle retries. No elaborate retry/backoff machinery for the capstone.

---

## 2. Shared Data Types

```python
# backend/market/types.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    """A single price observation for one ticker."""
    ticker: str
    price: float
    prev_price: float
    timestamp: str  # ISO-8601 UTC, e.g. "2024-01-01T10:00:00Z"

    @property
    def direction(self) -> str:
        if self.price > self.prev_price:
            return "up"
        if self.price < self.prev_price:
            return "down"
        return "unchanged"

    def to_event(self) -> dict:
        """Shape pushed over SSE (matches PLAN.md §6)."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.prev_price,
            "timestamp": self.timestamp,
            "direction": self.direction,
        }
```

---

## 3. The Price Cache

A thin in-memory store. It owns the `price → prev_price` transition so every
source just submits "the new price for ticker X" and the cache produces the
`Quote`.

```python
# backend/market/cache.py
from datetime import datetime, timezone
from .types import Quote


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class PriceCache:
    """Latest Quote per ticker. Single writer (the active source), many readers (SSE)."""

    def __init__(self) -> None:
        self._quotes: dict[str, Quote] = {}

    def update(self, ticker: str, price: float) -> Quote:
        """Record a new price; prev_price carries over from the last quote."""
        prev = self._quotes[ticker].price if ticker in self._quotes else price
        quote = Quote(ticker=ticker, price=price, prev_price=prev, timestamp=_now_iso())
        self._quotes[ticker] = quote
        return quote

    def get(self, ticker: str) -> Quote | None:
        return self._quotes.get(ticker)

    def snapshot(self) -> dict[str, Quote]:
        return dict(self._quotes)
```

Notes:
- First time a ticker is seen, `prev_price == price` → `direction == "unchanged"`,
  so the frontend does not flash on the initial value.
- `current_price` for portfolio math (`/api/portfolio`) reads `cache.get(ticker).price`.

---

## 4. The Abstract Source

The base class owns the background loop; subclasses implement a single
`fetch(tickers)` coroutine that returns `{ticker: price}`. The loop interval
differs per source.

```python
# backend/market/source.py
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
```

The broad `except` here is the **one** deliberate exception manager: a transient
network error on the Massive path must not tear down the price feed. It logs and
the next cycle retries — no backoff machinery.

---

## 5. The Two Implementations

### 5a. Massive poller

```python
# backend/market/massive.py
import os
import httpx
from .source import MarketDataSource

BASE_URL = "https://api.massive.com"


class MassiveSource(MarketDataSource):
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
    for section, key in (("lastTrade", "p"), ("min", "c"), ("day", "c"), ("prevDay", "c")):
        value = (snap.get(section) or {}).get(key)
        if value:
            return float(value)
    return None
```

One request per 15 s covers every watched ticker. Newly added tickers join the
union and appear on the next cycle (the `prices.flash` gap is acceptable per
`PLAN.md`). Price selection and fallbacks are detailed in `MASSIVE_API.md` §3.

### 5b. Simulator

```python
# backend/market/simulator.py
from .source import MarketDataSource
# ... GBM engine in MARKET_SIMULATOR.md ...


class SimulatorSource(MarketDataSource):
    interval_seconds = 0.5  # smooth, real-time-feeling motion

    def __init__(self, cache, get_tickers) -> None:
        super().__init__(cache, get_tickers)
        self._engine = GbmEngine()

    async def fetch(self, tickers: set[str]) -> dict[str, float]:
        return self._engine.step(tickers)  # synchronous GBM step; no I/O
```

The simulator's `fetch` does no I/O, so the loop's `await asyncio.sleep` is the
only suspension point. Full engine design in `MARKET_SIMULATOR.md`.

---

## 6. The Factory — Source Selection

```python
# backend/market/__init__.py
import os
from collections.abc import Callable
from .cache import PriceCache
from .source import MarketDataSource
from .massive import MassiveSource
from .simulator import SimulatorSource


def create_source(cache: PriceCache, get_tickers: Callable[[], set[str]]) -> MarketDataSource:
    """Massive when MASSIVE_API_KEY is set and non-empty, else the simulator."""
    if os.environ.get("MASSIVE_API_KEY", "").strip():
        return MassiveSource(cache, get_tickers)
    return SimulatorSource(cache, get_tickers)
```

The choice is made once at startup. Nothing else in the codebase branches on the
data source.

---

## 7. Wiring into FastAPI Lifespan

```python
# backend/main.py (sketch)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .market import PriceCache, create_source
from . import watchlist, positions

cache = PriceCache()


def current_tickers() -> set[str]:
    """Live union of watchlist tickers and held-position tickers."""
    return watchlist.tickers() | positions.held_tickers()


@asynccontextmanager
async def lifespan(app: FastAPI):
    source = create_source(cache, current_tickers)
    await source.start()
    try:
        yield
    finally:
        await source.stop()


app = FastAPI(lifespan=lifespan)
```

The SSE endpoint reads from `cache.snapshot()` on its own cadence (~500 ms) and
emits `Quote.to_event()` JSON, independent of how fast the source refreshes:

```python
# backend/routes/stream.py (sketch)
import asyncio, json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/api/stream/prices")
async def stream_prices():
    async def gen():
        while True:
            for quote in cache.snapshot().values():
                yield f"data: {json.dumps(quote.to_event())}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")
```

With the simulator the cache changes every 0.5 s, so SSE pushes fresh prices each
tick. With Massive the cache changes every 15 s, so SSE re-pushes the same value
for ~30 ticks — the frontend only flashes when `price != prev_price`, so repeated
identical pushes are silent. This is exactly the behavior `PLAN.md` §6 calls for.

---

## 8. Interface Contract Summary

| Concern | Contract |
|---------|----------|
| Selection | `MASSIVE_API_KEY` set & non-empty → Massive; else simulator |
| Writer | exactly one `MarketDataSource` background task writes the cache |
| Readers | SSE (and portfolio current-price lookups) read `PriceCache` |
| Ticker set | `get_tickers()` callback, evaluated every cycle (watchlist ∪ positions) |
| Output unit | `Quote(ticker, price, prev_price, timestamp)` → `direction` derived |
| Cadence | simulator 0.5 s; Massive 15 s; SSE push 0.5 s (decoupled) |
| Failure | one bad cycle logs and is skipped; loop continues |

Both implementations satisfy the same `MarketDataSource.fetch(tickers) ->
{ticker: price}` contract, which is the only thing the rest of the system relies
on. This is also what the unit tests target (per `PLAN.md` §12): both sources
produce valid prices and conform to the abstract interface.
