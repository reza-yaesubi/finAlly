# Market Data Backend — Code Review

**Reviewer:** Claude (Opus 4.8)
**Date:** 2026-06-25
**Scope:** `backend/market/` (types, cache, source, massive, simulator, sim_engine,
sim_universe, `__init__`), `backend/tests/test_market.py`, `backend/pyproject.toml`
**Reference docs:** `PLAN.md`, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md`

---

## Resolution (2026-06-25)

All findings below have been fixed. `uv run --extra test pytest` now runs the
suite and reports **52 passed** (the 49 originals, the repaired
`test_zero_sigma_pure_drift`, and two new unknown-ticker reproducibility tests).

- MD-1 — `[tool.uv] package = false` added to `pyproject.toml`; standard test
  command works.
- MD-2 — `test_zero_sigma_pure_drift` now compares against the rounded drift.
- MD-3 — unknown-ticker start price uses `hashlib.sha256` (process-stable);
  added `test_unknown_ticker_start_price_is_deterministic` and
  `test_unknown_ticker_reproducible_with_same_seed`.
- MD-4 — `stop()` now awaits task cancellation.
- MD-7 — `MassiveSource` raises a clear `ValueError` when the key is missing.
- MD-8 — removed the always-true no-op assertion.

The findings are retained below as the original review record.

---

## Verdict

The implementation is clean, small, and matches the design docs closely. The
abstraction (`PriceCache` + abstract `MarketDataSource` + two implementations +
`create_source` factory) is exactly what `MARKET_INTERFACE.md` specifies, and the
code is readable with good docstrings and no overengineering.

**However, it does not ship as-is:**

1. The canonical test command `uv run pytest` **fails** because the project can't
   be built (packaging misconfiguration). — **HIGH**
2. One unit test **fails** on a correct run (`test_zero_sigma_pure_drift`). — **MEDIUM**
3. Unknown-ticker starting prices are **not reproducible** across processes despite
   the seed, because `hash()` is salted per process. — **MEDIUM**

Fix these three and the module is in good shape.

---

## Test Results

The documented workflow fails:

```
$ uv run --extra test pytest
ValueError: Unable to determine which files to ship inside the wheel ...
The most likely cause of this is that there is no directory that matches
the name of your project (finally_backend).
```

`uv run` tries to build the local project (`finally-backend`) as a wheel, but the
package directory is `market/`, not `finally_backend/`, and there is no
`[tool.hatch.build.targets.wheel]` or `[tool.uv] package = false` to tell the
build system otherwise. **The test suite cannot be run via the standard command.**

Running with the local build skipped (`uv run --no-project --with pytest
--with pytest-asyncio --with respx --with httpx python -m pytest`):

```
49 passed, 1 failed in 3.48s
```

- **49 pass** — Quote, PriceCache, most of GbmEngine, SimulatorSource,
  `_pick_price`, MassiveSource HTTP behavior, loop resilience, and the factory.
- **1 fails** — `TestGbmEngine::test_zero_sigma_pure_drift` (see MD-2).

---

## Findings

### HIGH

**MD-1 — `uv run pytest` is broken (packaging).** `backend/pyproject.toml:1-12`
The project name `finally-backend` normalizes to `finally_backend`; hatchling
looks for a directory of that name to build a wheel and fails. This blocks the
standard `uv run pytest` / `uv sync` workflow that `PLAN.md` (uv-managed project)
and the course assume.

*Root cause (proven):* the hatchling traceback states it cannot determine wheel
files because no directory matches the project name. The actual package is
`market/`.

*Fix (this is an application, not a distributable library — simplest):*
```toml
[tool.uv]
package = false
```
*Or, if a build is desired:*
```toml
[tool.hatch.build.targets.wheel]
packages = ["market"]
```
Either makes `uv run pytest` work. Confirmed the tests run and pass (bar MD-2)
once the local build is bypassed.

---

### MEDIUM

**MD-2 — `test_zero_sigma_pure_drift` fails on every correct run.**
`backend/tests/test_market.py:184-197`, engine at `backend/market/sim_engine.py:60`

The test asserts the post-step price equals `start * exp(mu·dt·SPEED)` to within
`1e-6`. But `step()` ends with `round(max(new_price, 0.01), 2)`. For a $100 stock
the one-tick drift is:

```
100 · (exp(0.10 · DT · 60) − 1) = 5.09e-5   →   rounds to 100.00
```

So the rounded result is `100.0`, the unrounded expectation is `100.0000508…`,
and the assertion fails by `5.09e-5` (> `1e-6`). This is **proven**, not theoretical.

*Root cause:* per-tick drift (~5e-5) is two orders of magnitude smaller than the
1-cent rounding granularity, so rounding erases it. The test ignores the rounding
the engine applies.

*Fix options:* (a) compare against the **rounded** expectation
(`round(start·exp(mu·dt·SPEED), 2)`), which makes the test assert the real
contract; or (b) make the test use a price/horizon where drift exceeds a cent
(e.g. multiple steps, or a much larger `mu`/`SPEED`) before comparing. Option (a)
is the honest fix but it then only proves "drift is negligible per tick," which
leads to MD-5.

**MD-3 — Unknown-ticker start price is not reproducible across processes.**
`backend/market/sim_engine.py:30`

```python
start = 50 + (hash(ticker) % 450)
```

`MARKET_SIMULATOR.md` and the seeded `random.Random(seed)` promise
reproducibility, and `test_reproducibility_with_same_seed` passes — but only
because it uses seed-universe tickers (`AAPL`, `TSLA`) whose start prices are
constants. For an **ad-hoc** ticker, the starting price depends on Python's
built-in `str.__hash__`, which is **salted per process** (`PYTHONHASHSEED`).

*Proven:* `hash('ZZZZ')` returned three different values across three process
invocations. Two runs with the same engine `seed` will therefore produce
different price streams for any non-seed ticker.

*Fix:* derive the start deterministically, e.g.
```python
import hashlib
start = 50 + int(hashlib.sha256(ticker.encode()).hexdigest(), 16) % 450
```
or draw it from the seeded RNG (`self._rng`). Add a reproducibility test that
uses an unknown ticker to lock this in.

---

### LOW / Minor

**MD-4 — `stop()` cancels the task but never awaits it.**
`backend/market/source.py:39-42`. `self._task.cancel()` is fire-and-forget; the
coroutine may not have unwound when `stop()` returns, and in `MassiveSource.stop`
the `httpx` client is closed immediately after, so an in-flight request could be
cancelled mid-close. Prefer awaiting the cancellation:
```python
async def stop(self):
    if self._task:
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
```
Harmless for the simulator; tidier for clean FastAPI lifespan shutdown.

**MD-5 — Per-tick drift is negligible (design note).** With `DT·SPEED ≈ 5.1e-6`,
drift moves a $100 price by ~5e-5/tick and rounds away entirely; only the
volatility term (`σ·√(dt·SPEED)·z`, ~8¢ per 1σ on a $100 name) produces visible
motion. That's fine for a demo (vol dominates real intraday moves too), but `mu`
is currently almost inert. If the long-run drift in `SEED_UNIVERSE` is meant to be
felt, raise `SPEED` or rethink `DT`. Worth a one-line comment so it isn't mistaken
for a bug later.

**MD-6 — Low-priced tickers can stall.** The 1σ move scales with price, so a sub-
~$6 ad-hoc ticker often moves <1¢ and rounds to "unchanged" for many ticks
(persistent `direction == "unchanged"`, flat sparkline). Seed-universe prices are
all high enough to be unaffected; only relevant if cheap tickers are added.

**MD-7 — `MassiveSource.__init__` will `KeyError` if the key is unset.**
`backend/market/massive.py:17` reads `os.environ['MASSIVE_API_KEY']` directly.
`create_source` guards this, so it's safe through the intended path, but direct
construction (or a future caller) crashes with a bare `KeyError`. Minor.

**MD-8 — Two weak tests.**
- `test_state_persists_between_steps` (`test_market.py:206`) ends with
  `assert ... != p1 or True`, which is **always true** — it asserts nothing. The
  intended check (state advanced) is on the line above; drop the no-op line.
- `_pick_price`'s `if value:` treats `0` as "no price" (`test_market.py:301-307`
  relies on this). Correct for stocks, but it would also reject a legitimately
  falsy value; fine here, just noting the truthiness assumption.

**MD-9 — Timestamp granularity is whole seconds.** `backend/market/cache.py:6`
uses `timespec="seconds"`, so the simulator's two ticks/second share a timestamp.
The frontend flashes on price change (not timestamp) per `PLAN.md §6`, so this is
acceptable; flagged only in case any consumer keys off the timestamp.

---

## Spec Conformance

| Requirement (PLAN / design docs) | Status |
|---|---|
| `Quote` shape `{ticker, price, prev_price, timestamp, direction}` (PLAN §6) | Met (`types.py`, `to_event`) |
| Direction only `up`/`down`/`unchanged` | Met |
| First price → `prev_price == price` (no spurious flash) | Met (`cache.py:17`) |
| Single writer, in-memory cache, SSE reads snapshot | Met |
| `MASSIVE_API_KEY` set & non-empty → Massive, else simulator | Met, incl. empty/whitespace handling (`__init__.py`, tested) |
| Massive: one multi-ticker snapshot call, 15s interval, Bearer auth | Met (`massive.py`) |
| Price priority `lastTrade.p → min.c → day.c → prevDay.c` | Met & tested (`_pick_price`) |
| Simulator: GBM, correlation, events, seedable, no deps, 0.5s | Met, except reproducibility gap MD-3 |
| Loop survives a failed cycle | Met & tested (`test_loop_continues_after_fetch_exception`) |
| Empty ticker set → no fetch | Met & tested |

Functionally faithful to the design. The gaps are the reproducibility caveat
(MD-3) and the test/packaging issues, not interface drift.

---

## What's Good

- Clean separation: cache / abstract source / two impls / factory — matches
  `MARKET_INTERFACE.md` precisely.
- The single deliberate `except Exception` in the loop is well-placed and
  well-commented; no other defensive clutter.
- `_pick_price` fallback chain is correct and thoroughly tested, including the
  `0`-is-falsy and string-coercion cases.
- Good async test coverage (start/stop, loop resilience, empty-set skip) and
  HTTP mocking via `respx` (auth header, sorted tickers, parsing, error path).
- Sensible, documented tuning constants in `sim_engine.py`.

---

## Recommended Actions (in order)

1. **MD-1** — add `[tool.uv] package = false` (or a hatch wheel target) so
   `uv run pytest` works. *Blocker.*
2. **MD-3** — make unknown-ticker start price deterministic (hashlib or seeded
   RNG); add an unknown-ticker reproducibility test.
3. **MD-2** — fix `test_zero_sigma_pure_drift` to compare against the rounded
   value (or a horizon where drift exceeds a cent).
4. **MD-8** — remove the no-op assertion in `test_state_persists_between_steps`.
5. **MD-4 / MD-7** — await task cancellation in `stop()`; read the API key with a
   clear error if missing.
6. Re-run the full suite and confirm **50 passed**.

---

## How to Reproduce This Review

```bash
cd backend
# Standard command (currently fails — MD-1):
uv run --extra test pytest

# Workaround used to obtain results (bypasses the local build):
uv run --no-project --with pytest --with pytest-asyncio --with respx --with httpx \
  python -m pytest -q
# -> 49 passed, 1 failed
```
