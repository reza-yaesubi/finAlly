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
