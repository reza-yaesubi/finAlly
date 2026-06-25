# Massive API (formerly Polygon.io) — Reference for FinAlly

Research notes and code examples for retrieving real-time and end-of-day stock
prices for multiple tickers. This is the source data layer behind the optional
`MASSIVE_API_KEY` path described in `PLAN.md`.

> **Rebrand note.** Polygon.io rebranded to **Massive** on 2025-10-30. The new
> base URL is `https://api.massive.com`; the old `https://api.polygon.io` host
> still works and existing API keys are unchanged. The official Python client
> package was renamed from `polygon-api-client` to `massive`. All endpoint
> paths below are identical on both hosts.

---

## 1. Authentication

The API key is accepted two ways — both are equivalent:

| Method | How |
|--------|-----|
| Query parameter | append `?apiKey=YOUR_KEY` to the URL |
| Bearer header | `Authorization: Bearer YOUR_KEY` |

For FinAlly we use the **Bearer header** — it keeps the key out of URLs and logs.

```bash
# Header style (preferred)
curl -H "Authorization: Bearer $MASSIVE_API_KEY" \
  "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL"

# Query-param style (equivalent)
curl "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL&apiKey=$MASSIVE_API_KEY"
```

---

## 2. Rate Limits & Data Recency

| Plan | Requests / min | Price recency |
|------|----------------|---------------|
| Basic (free) | **5 / min** | End-of-day + 15-min delayed snapshots |
| Starter / Developer | higher | 15-min delayed |
| Advanced / Business | unlimited | real-time |

**Design consequence:** the free tier's 5 req/min budget is why FinAlly polls
**one snapshot request covering all watched tickers every 15 seconds** rather
than one request per ticker. One multi-ticker call per cycle stays comfortably
inside the limit. See `MARKET_INTERFACE.md` for the poller design.

---

## 3. The Endpoint We Actually Use — Multi-Ticker Snapshot

This is the workhorse for FinAlly: **one request returns the latest data for a
comma-separated list of tickers.**

```
GET /v2/snapshot/locale/us/markets/stocks/tickers
```

### Query parameters

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `tickers` | string | No | Comma-separated, **case-sensitive**: `AAPL,TSLA,GOOGL`. Omit for the entire market (10,000+ tickers). |
| `include_otc` | bool | No | Include OTC securities. Default `false`. |

### Response shape

```json
{
  "status": "OK",
  "count": 1,
  "tickers": [
    {
      "ticker": "AAPL",
      "day":      { "o": 20.64, "h": 20.64, "l": 20.51, "c": 20.51, "v": 37216, "vw": 20.62 },
      "prevDay":  { "o": 20.79, "h": 21.00, "l": 20.50, "c": 20.63, "v": 292738, "vw": 20.69 },
      "min":      { "t": 1684428600000, "o": 20.51, "h": 20.51, "l": 20.51, "c": 20.51, "v": 5000, "vw": 20.51, "n": 1, "av": 37216 },
      "lastTrade":{ "p": 20.506, "s": 2416, "t": 1605192894630916600, "x": 4, "i": "71675577320245", "c": [14, 41] },
      "lastQuote":{ "p": 20.50, "s": 13, "P": 20.60, "S": 22, "t": 1605192959994246100 },
      "todaysChange": -0.124,
      "todaysChangePerc": -0.601,
      "updated": 1605192894630916600
    }
  ]
}
```

### Fields that matter for FinAlly

| Field | Meaning | Use |
|-------|---------|-----|
| `ticker` | Symbol | cache key |
| `lastTrade.p` | Last trade **price** | the price we publish over SSE |
| `min.c` | Most recent 1-minute close | fallback when `lastTrade` is absent (delayed plans) |
| `day.c` | Current session close-so-far | secondary fallback |
| `prevDay.c` | Previous session close | baseline / sanity check |
| `todaysChangePerc` | % change vs prev close | optional display |
| `updated` | Last-update timestamp, **Unix nanoseconds** | freshness |

**Price selection order** (most to least real-time): `lastTrade.p` → `min.c` →
`day.c` → `prevDay.c`. On the free/delayed tiers `lastTrade` may be missing or
stale, so the fallback chain matters.

> **Timestamp units gotcha.** `lastTrade.t`, `lastQuote.t`, and `updated` are in
> **nanoseconds**. The aggregate-bar `t` and `min.t` are in **milliseconds**.
> Divide accordingly before constructing an ISO timestamp.

### Python example (httpx — what the backend uses)

```python
import os
import httpx

BASE_URL = "https://api.massive.com"
HEADERS = {"Authorization": f"Bearer {os.environ['MASSIVE_API_KEY']}"}


def fetch_snapshots(tickers: list[str]) -> dict[str, float]:
    """Return {ticker: latest_price} for the given tickers in one request."""
    url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
    params = {"tickers": ",".join(tickers)}
    resp = httpx.get(url, params=params, headers=HEADERS, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()

    prices: dict[str, float] = {}
    for snap in data.get("tickers", []):
        price = _pick_price(snap)
        if price is not None:
            prices[snap["ticker"]] = price
    return prices


def _pick_price(snap: dict) -> float | None:
    """Most real-time price available, with fallbacks for delayed plans."""
    for path in (("lastTrade", "p"), ("min", "c"), ("day", "c"), ("prevDay", "c")):
        section = snap.get(path[0]) or {}
        value = section.get(path[1])
        if value:
            return float(value)
    return None
```

The async version used by the background poller:

```python
async def fetch_snapshots_async(client: httpx.AsyncClient, tickers: list[str]) -> dict[str, float]:
    url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
    resp = await client.get(url, params={"tickers": ",".join(tickers)}, headers=HEADERS)
    resp.raise_for_status()
    return {
        s["ticker"]: p
        for s in resp.json().get("tickers", [])
        if (p := _pick_price(s)) is not None
    }
```

---

## 4. Single-Ticker Snapshot

When only one symbol is needed (e.g. a detail lookup), use:

```
GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}
```

`stocksTicker` is case-sensitive (e.g. `AAPL`). The response wraps a single
object under a `ticker` key with the same `day` / `min` / `lastTrade` /
`lastQuote` / `prevDay` / `todaysChange` / `updated` fields as above. FinAlly
prefers the multi-ticker snapshot, so this is documented for completeness only.

---

## 5. End-of-Day Prices

Two relevant endpoints.

### 5a. Previous Day Bar — `prevDay` close for one ticker

```
GET /v2/aggs/ticker/{stocksTicker}/prev
```

| Param | Notes |
|-------|-------|
| `adjusted` | split-adjust, default `true` |

```json
{
  "ticker": "AAPL",
  "status": "OK",
  "resultsCount": 1,
  "results": [
    { "o": 115.55, "h": 117.59, "l": 114.13, "c": 115.97, "v": 131704427, "vw": 116.31, "t": 1605042000000 }
  ]
}
```

`results[0].c` is the previous trading day's closing price. `t` is in
**milliseconds**.

### 5b. Custom Aggregate Bars — historical OHLC ranges

For seeding charts or backfilling history:

```
GET /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
```

| Param | Required | Notes |
|-------|----------|-------|
| `stocksTicker` | yes | case-sensitive symbol |
| `multiplier` | yes | size of the timespan multiplier (e.g. `1`) |
| `timespan` | yes | `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year` |
| `from`, `to` | yes | `YYYY-MM-DD` or ms timestamp |
| `adjusted` | no | default `true` |
| `sort` | no | `asc` (default) or `desc` |
| `limit` | no | default 5000, max 50000 |

```bash
# One daily bar per day, Jan 2024
curl -H "Authorization: Bearer $MASSIVE_API_KEY" \
  "https://api.massive.com/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31"
```

```json
{
  "ticker": "AAPL",
  "adjusted": true,
  "status": "OK",
  "queryCount": 21,
  "resultsCount": 21,
  "results": [
    { "o": 74.06, "h": 75.15, "l": 73.80, "c": 75.09, "v": 135647456, "vw": 74.61, "t": 1577941200000, "n": 1 }
  ],
  "next_url": "https://api.massive.com/v2/aggs/...&cursor=..."
}
```

Bar fields: `o/h/l/c` (OHLC), `v` (volume), `vw` (volume-weighted avg price),
`t` (start of bar, **ms**), `n` (transaction count). Pagination via `next_url`.

> FinAlly accumulates intraday sparkline/chart data from the SSE stream since
> page load (per `PLAN.md`), so aggregate-bar backfill is **not required** for
> the core build. Endpoint 5b is documented as an optional enhancement.

---

## 6. Official Python Client (alternative to raw httpx)

```bash
uv add massive
```

```python
from massive import RESTClient

client = RESTClient(api_key=os.environ["MASSIVE_API_KEY"])
snapshots = client.get_snapshot_all("stocks", tickers=["AAPL", "GOOGL", "MSFT"])
for s in snapshots:
    print(s.ticker, s.last_trade.price)
```

**FinAlly uses raw `httpx` instead of the client library** — it keeps the
dependency surface small, makes the async polling loop explicit, and the only
endpoint we hit is a single well-understood GET. The client library is noted
here as a valid alternative.

---

## 7. Summary for FinAlly

- **One endpoint** drives live prices: the multi-ticker snapshot
  `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=...`.
- **One request per poll cycle** covers all watched tickers — fits the free
  tier's 5 req/min budget when polling every 15 s.
- **Price = `lastTrade.p`** with fallbacks `min.c` → `day.c` → `prevDay.c`.
- **Auth** via `Authorization: Bearer` header.
- The poller feeds the shared in-memory price cache that SSE reads from; the
  rest of the system is agnostic to the data source. See
  `MARKET_INTERFACE.md`.

## Sources

- [Massive — Full Market Snapshot docs](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Massive — Single Ticker Snapshot docs](https://massive.com/docs/rest/stocks/snapshots/single-ticker-snapshot)
- [Massive — Custom Bars (Aggregates) docs](https://massive.com/docs/rest/stocks/aggregates/custom-bars)
- [Massive — Previous Day Bar docs](https://massive.com/docs/rest/stocks/aggregates/previous-day-bar)
- [Massive — request limit knowledge base](https://polygon.io/knowledge-base/article/what-is-the-request-limit-for-polygons-restful-apis)
- [massive-com/client-python (official Python client)](https://github.com/massive-com/client-python)
