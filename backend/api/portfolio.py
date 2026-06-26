"""
Portfolio API endpoints — positions, trades, history.
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db
from market import PriceCache

log = logging.getLogger("api.portfolio")

router = APIRouter()

_cache: PriceCache | None = None


def init(cache: PriceCache) -> None:
    global _cache
    _cache = cache


def _get_current_price(ticker: str) -> float:
    if _cache:
        quote = _cache.get(ticker)
        if quote:
            return quote.price
    return 0.0


def _build_portfolio(user_id: str = "default") -> dict:
    cash = db.get_cash(user_id)
    positions_raw = db.get_positions(user_id)
    positions = []
    holdings_value = 0.0
    for pos in positions_raw:
        if pos["quantity"] <= 0:
            continue
        current_price = _get_current_price(pos["ticker"])
        unrealized_pnl = (current_price - pos["avg_cost"]) * pos["quantity"]
        pnl_pct = (current_price - pos["avg_cost"]) / pos["avg_cost"] * 100 if pos["avg_cost"] else 0.0
        holdings_value += pos["quantity"] * current_price
        positions.append({
            "ticker": pos["ticker"],
            "quantity": pos["quantity"],
            "avg_cost": pos["avg_cost"],
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "pnl_pct": pnl_pct,
        })
    total_value = cash + holdings_value
    return {"cash": cash, "total_value": total_value, "positions": positions}


@router.get("/portfolio")
def get_portfolio():
    return _build_portfolio()


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]


@router.post("/portfolio/trade")
def execute_trade(req: TradeRequest):
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "Quantity must be positive"})

    ticker = req.ticker.upper()
    current_price = _get_current_price(ticker)
    if current_price <= 0:
        raise HTTPException(status_code=400, detail={"ok": False, "error": f"No price available for {ticker}"})

    cash = db.get_cash()
    positions_raw = db.get_positions()
    pos_map = {p["ticker"]: p for p in positions_raw}

    if req.side == "buy":
        cost = req.quantity * current_price
        if cost > cash:
            raise HTTPException(status_code=400, detail={"ok": False, "error": "Insufficient cash"})
        new_cash = cash - cost
        db.update_cash(new_cash)

        existing = pos_map.get(ticker)
        if existing and existing["quantity"] > 0:
            new_qty = existing["quantity"] + req.quantity
            new_avg = (existing["quantity"] * existing["avg_cost"] + req.quantity * current_price) / new_qty
        else:
            new_qty = req.quantity
            new_avg = current_price
        db.upsert_position(ticker, new_qty, new_avg)

    else:  # sell
        existing = pos_map.get(ticker)
        if not existing or existing["quantity"] < req.quantity:
            raise HTTPException(status_code=400, detail={"ok": False, "error": "Insufficient shares"})
        proceeds = req.quantity * current_price
        new_cash = cash + proceeds
        db.update_cash(new_cash)
        new_qty = existing["quantity"] - req.quantity
        db.upsert_position(ticker, new_qty, existing["avg_cost"])

    db.record_trade(ticker, req.side, req.quantity, current_price)

    # Snapshot portfolio value immediately after trade
    portfolio = _build_portfolio()
    db.record_snapshot(portfolio["total_value"])

    return {
        "ok": True,
        "ticker": ticker,
        "side": req.side,
        "quantity": req.quantity,
        "price": current_price,
        "cash_remaining": db.get_cash(),
    }


@router.get("/portfolio/history")
def get_history():
    return db.get_snapshots()
