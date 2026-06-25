import math
import random
from dataclasses import dataclass
from .sim_universe import SEED_UNIVERSE, DEFAULT_SPEC, TickerSpec

SECONDS_PER_TRADING_YEAR = 252 * 6.5 * 3600
DT = 0.5 / SECONDS_PER_TRADING_YEAR
SPEED = 60.0                 # demo exaggeration multiplier on dt
EVENT_PROB = 0.0005          # per-tick chance of a shock
W_MARKET, W_SECTOR, W_IDIO = 0.4, 0.3, 0.3


@dataclass
class _State:
    price: float
    spec: TickerSpec


class GbmEngine:
    """Stateful GBM price generator with sector correlation and random events."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._state: dict[str, _State] = {}

    def _ensure(self, ticker: str) -> _State:
        if ticker not in self._state:
            spec = SEED_UNIVERSE.get(ticker)
            if spec is None:
                start = 50 + (hash(ticker) % 450)
                spec = TickerSpec(float(start), DEFAULT_SPEC.mu, DEFAULT_SPEC.sigma, "other")
            self._state[ticker] = _State(price=spec.price, spec=spec)
        return self._state[ticker]

    def step(self, tickers: set[str]) -> dict[str, float]:
        """Advance every requested ticker one tick; return {ticker: new_price}."""
        z_market = self._rng.gauss(0, 1)
        z_sector: dict[str, float] = {}

        prices: dict[str, float] = {}
        for ticker in tickers:
            st = self._ensure(ticker)
            sector = st.spec.sector
            if sector not in z_sector:
                z_sector[sector] = self._rng.gauss(0, 1)

            z = (W_MARKET * z_market
                 + W_SECTOR * z_sector[sector]
                 + W_IDIO * self._rng.gauss(0, 1))

            dt = DT * SPEED
            mu, sigma = st.spec.mu, st.spec.sigma
            drift = (mu - 0.5 * sigma * sigma) * dt
            shock = sigma * math.sqrt(dt) * z
            new_price = st.price * math.exp(drift + shock)

            if self._rng.random() < EVENT_PROB:
                new_price *= 1 + self._rng.choice([-1, 1]) * self._rng.uniform(0.02, 0.05)

            new_price = round(max(new_price, 0.01), 2)
            st.price = new_price
            prices[ticker] = new_price
        return prices
