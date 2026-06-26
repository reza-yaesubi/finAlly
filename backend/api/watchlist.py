"""
Watchlist API endpoints.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

import db

router = APIRouter()


@router.get("/watchlist")
def get_watchlist():
    tickers = db.get_watchlist()
    return [{"ticker": t} for t in tickers]


class WatchlistAddRequest(BaseModel):
    ticker: str


@router.post("/watchlist", status_code=201)
def add_to_watchlist(req: WatchlistAddRequest):
    ticker = req.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail={"error": "Ticker is required"})
    try:
        db.add_to_watchlist(ticker)
    except ValueError:
        raise HTTPException(status_code=409, detail={"error": "Ticker already in watchlist"})
    return {"ticker": ticker}


@router.delete("/watchlist/{ticker}", status_code=204)
def remove_from_watchlist(ticker: str):
    db.remove_from_watchlist(ticker.upper())
    return Response(status_code=204)
