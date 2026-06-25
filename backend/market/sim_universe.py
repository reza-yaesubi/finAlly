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
