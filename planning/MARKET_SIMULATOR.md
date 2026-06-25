# Market Simulator — Geometric Brownian Motion Price Engine

The approach and code structure for the built-in price simulator that runs when
`MASSIVE_API_KEY` is **not** set. It produces realistic, continuously moving
prices with no external dependencies, so FinAlly works out of the box.

Companion docs: `MARKET_INTERFACE.md` (how the simulator plugs in),
`MASSIVE_API.md` (the real-data alternative).

---

## 1. Goals

- **Realistic-looking motion** — prices wander like real stocks, not random
  noise. Geometric Brownian Motion (GBM) gives log-normal, always-positive,
  percentage-based moves.
- **Self-contained** — pure Python + `random`, no network, no numpy required.
- **Visually engaging** — correlated sector moves and occasional dramatic events
  make the terminal feel alive for the demo.
- **Deterministic-friendly** — accepts a seed so tests are reproducible.
- **Cheap** — a `step()` is O(number of tickers), called every 0.5 s.

---

## 2. The Math — Geometric Brownian Motion

The standard model for stock prices. Over a small time step `dt`, a price `S`
evolves as:

```
S(t + dt) = S(t) * exp( (mu - 0.5 * sigma^2) * dt  +  sigma * sqrt(dt) * Z )
```

| Symbol | Meaning | FinAlly value |
|--------|---------|---------------|
| `mu` | drift — annualized expected return | small per-ticker, e.g. 0.05–0.15 |
| `sigma` | volatility — annualized std-dev of returns | per-ticker, e.g. 0.20–0.60 |
| `dt` | time step as a fraction of a year | one tick = 0.5 s |
| `Z` | standard normal random draw | `random.gauss(0, 1)` |

Because the multiplier is `exp(...)`, prices stay strictly positive and moves are
proportional to the current price — a $190 stock and a $5 stock both move in
realistic percentage terms.

### Choosing `dt`

Ticks fire every 0.5 s. To keep per-tick moves visible but not wild, treat each
tick as a slice of a trading year. A simple, tunable choice:

```python
SECONDS_PER_TRADING_YEAR = 252 * 6.5 * 3600  # ~5.9M trading seconds/year
DT = 0.5 / SECONDS_PER_TRADING_YEAR
```

With realistic `sigma`, this yields small smooth per-tick moves. `dt` (or a
"speed" multiplier on it) is the single knob to make motion calmer or livelier
for the demo — multiply `DT` by, say, 50–100 to exaggerate movement on screen
without changing the model.

---

## 3. Seed Universe

Each ticker starts from a realistic price and gets its own drift/volatility and a
**sector tag** used for correlation (§4).

```python
# backend/market/sim_universe.py
from dataclasses import dataclass


@dataclass
class TickerSpec:
    price: float       # seed / starting price
    mu: float          # annualized drift
    sigma: float       # annualized volatility
    sector: str        # for correlated moves


SEED_UNIVERSE: dict[str, TickerSpec] = {
    "AAPL":  TickerSpec(190.0, 0.10, 0.28, "tech"),
    "GOOGL": TickerSpec(175.0, 0.09, 0.30, "tech"),
    "MSFT":  TickerSpec(420.0, 0.11, 0.26, "tech"),
    "AMZN":  TickerSpec(185.0, 0.10, 0.34, "tech"),
    "TSLA":  TickerSpec(250.0, 0.06, 0.60, "auto"),
    "NVDA":  TickerSpec(880.0, 0.18, 0.50, "tech"),
    "META":  TickerSpec(500.0, 0.12, 0.38, "tech"),
    "JPM":   TickerSpec(195.0, 0.06, 0.22, "finance"),
    "V":     TickerSpec(275.0, 0.07, 0.20, "finance"),
    "NFLX":  TickerSpec(630.0, 0.09, 0.40, "media"),
}

DEFAULT_SPEC = TickerSpec(100.0, 0.08, 0.35, "other")  # for ad-hoc added tickers
```

**Unknown tickers.** When the user adds a ticker outside the seed set (manually
or via the AI), the engine lazily creates state for it from `DEFAULT_SPEC` with a
deterministic-ish starting price (e.g. `50 + hash(ticker) % 450`), so any symbol
"just works".

---

## 4. Correlation & Events — the "alive" feel

Two embellishments on plain per-ticker GBM, both called for in `PLAN.md` §6.

### Correlated sector moves

Each tick, draw one **market factor** and one **per-sector factor** in addition
to each ticker's idiosyncratic noise. A ticker's `Z` blends them:

```
Z = w_market * z_market + w_sector * z_sector[sector] + w_idio * z_idio
```

with weights summing to 1 (e.g. `0.4 / 0.3 / 0.3`). This makes tech names tend to
rise and fall together while still moving individually — visually obvious in the
watchlist and convincing in the heatmap.

### Random dramatic events

With small probability per tick per ticker (e.g. `~0.0005`), inject a one-off
shock of ±2–5% on top of the GBM step. Gives the occasional eye-catching flash
without distorting long-run behavior.

---

## 5. Engine Structure

```python
# backend/market/sim_engine.py
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
```

### Why this structure

- **`step(tickers)` returns `{ticker: price}`** — exactly the shape
  `SimulatorSource.fetch` needs (`MARKET_INTERFACE.md` §5b). The engine knows
  nothing about the cache, SSE, or asyncio.
- **State lives in the engine**, keyed by ticker — last price persists between
  ticks, which is what makes it a walk rather than fresh random numbers.
- **Lazy `_ensure`** means any ticker the watchlist throws at it works.
- **Seedable `Random`** instance → reproducible tests without touching global
  random state.
- No numpy: `random.gauss` + `math.exp` is plenty for 10–30 tickers at 2 Hz.

---

## 6. How It Runs

The engine is driven by `SimulatorSource`, whose loop calls `step()` every
`interval_seconds = 0.5` and writes results to the `PriceCache`
(`MARKET_INTERFACE.md` §4–5). The cache derives `prev_price` and `direction`;
SSE pushes the resulting `Quote`s. The simulator is a pure in-process background
task — no external dependencies, matching `PLAN.md` §6.

---

## 7. Testing (per PLAN.md §12)

Deterministic with a fixed seed:

- **Valid prices** — every `step()` result is positive and finite for all
  tickers across many iterations.
- **GBM correctness** — over a large sample with `sigma=0`, prices follow pure
  drift `exp(mu*dt)` per tick (no randomness); with `mu=0`, the mean log-return
  is ~0. Verifies the drift/shock terms are wired correctly.
- **Reproducibility** — two engines with the same seed produce identical
  sequences.
- **Unknown tickers** — adding a symbol outside `SEED_UNIVERSE` produces a valid
  price stream from `DEFAULT_SPEC`.
- **Interface conformance** — `SimulatorSource.fetch(tickers)` returns
  `{ticker: float}` for exactly the requested set, satisfying the
  `MarketDataSource` contract shared with `MassiveSource`.

```python
def test_prices_stay_positive():
    engine = GbmEngine(seed=42)
    tickers = {"AAPL", "TSLA", "NVDA"}
    for _ in range(10_000):
        for price in engine.step(tickers).values():
            assert price > 0
```

---

## 8. Tunable Knobs (one place to adjust the demo)

| Constant | Effect |
|----------|--------|
| `SPEED` | bigger → larger per-tick moves (most visible knob) |
| `EVENT_PROB` | frequency of dramatic spikes |
| `W_MARKET / W_SECTOR / W_IDIO` | how tightly tickers move together |
| `TickerSpec.sigma` | per-ticker choppiness |
| `TickerSpec.mu` | per-ticker long-run trend |
| `interval_seconds` (in `SimulatorSource`) | tick rate / SSE smoothness |
