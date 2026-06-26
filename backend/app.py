"""
FinAlly — FastAPI application entry point.

Startup: initializes DB, starts market data source, starts snapshot background task.
Serves API routes under /api/* and static frontend files at /*.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import db
from market import PriceCache, create_source
from api import health, stream, portfolio, watchlist, chat

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

cache = PriceCache()


def get_tickers() -> set[str]:
    """Union of watchlist tickers and position tickers."""
    tickers = set(db.get_watchlist())
    for pos in db.get_positions():
        if pos["quantity"] > 0:
            tickers.add(pos["ticker"])
    return tickers


source = None
_snapshot_task: asyncio.Task | None = None


async def _snapshot_loop() -> None:
    """Record portfolio value every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            p = portfolio._build_portfolio()
            db.record_snapshot(p["total_value"])
        except Exception:
            log.exception("Portfolio snapshot failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global source, _snapshot_task

    db.init_db()

    portfolio.init(cache)
    stream.init(cache, get_tickers)

    source = create_source(cache, get_tickers)
    await source.start()
    log.info("Market data source started: %s", type(source).__name__)

    _snapshot_task = asyncio.create_task(_snapshot_loop())

    yield

    if _snapshot_task:
        _snapshot_task.cancel()
        try:
            await _snapshot_task
        except asyncio.CancelledError:
            pass

    if source:
        await source.stop()
        log.info("Market data source stopped")


app = FastAPI(title="FinAlly API", lifespan=lifespan)

app.include_router(health.router, prefix="/api")
app.include_router(stream.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# Serve static Next.js export at /* (only if the directory exists)
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.isdir(_static_dir):
    _static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
    log.info("Serving static files from: %s", _static_dir)
