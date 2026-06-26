"""
SSE streaming endpoint — pushes live price updates to the frontend.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from market import PriceCache

log = logging.getLogger("api.stream")

router = APIRouter()

# Injected by app.py at startup
_cache: PriceCache | None = None
_get_tickers: object = None  # Callable[[], set[str]]


def init(cache: PriceCache, get_tickers) -> None:
    global _cache, _get_tickers
    _cache = cache
    _get_tickers = get_tickers


@router.get("/stream/prices")
async def stream_prices(request: Request):
    """Long-lived SSE connection pushing price updates every 500ms."""

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                snapshot = _cache.snapshot() if _cache else {}
                tickers = _get_tickers() if _get_tickers else set()
                for ticker, quote in snapshot.items():
                    if ticker in tickers:
                        data = json.dumps(quote.to_event())
                        yield f"data: {data}\n\n"
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("SSE generator error")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
