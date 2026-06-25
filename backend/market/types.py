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
