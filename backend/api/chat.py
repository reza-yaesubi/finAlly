"""
Chat API endpoint — bridges user messages to the LLM and auto-executes actions.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

import db
import llm
from api.portfolio import _build_portfolio, _get_current_price

log = logging.getLogger("api.chat")

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(req: ChatRequest):
    portfolio_context = _build_portfolio()
    history = db.get_chat_history(limit=20)

    db.add_chat_message("user", req.message)

    result = await llm.chat(req.message, portfolio_context, history)

    executed_trades = []
    for trade in result.get("trades", []):
        executed = _execute_llm_trade(trade)
        executed_trades.append(executed)

    executed_watchlist = []
    for change in result.get("watchlist_changes", []):
        executed = _execute_llm_watchlist_change(change)
        executed_watchlist.append(executed)

    actions = {
        "trades": executed_trades,
        "watchlist_changes": executed_watchlist,
    }
    db.add_chat_message("assistant", result["message"], actions=actions)

    return {
        "message": result["message"],
        "trades": executed_trades,
        "watchlist_changes": executed_watchlist,
    }


def _execute_llm_trade(trade: dict) -> dict:
    ticker = trade.get("ticker", "").upper()
    side = trade.get("side", "")
    quantity = trade.get("quantity", 0)

    out = {"ticker": ticker, "side": side, "quantity": quantity}

    if not ticker or side not in ("buy", "sell") or quantity <= 0:
        out["status"] = "failed"
        out["error"] = "Invalid trade parameters"
        return out

    current_price = _get_current_price(ticker)
    if current_price <= 0:
        out["status"] = "failed"
        out["error"] = f"No price available for {ticker}"
        return out

    cash = db.get_cash()
    positions_raw = db.get_positions()
    pos_map = {p["ticker"]: p for p in positions_raw}

    if side == "buy":
        cost = quantity * current_price
        if cost > cash:
            out["status"] = "failed"
            out["error"] = "Insufficient cash"
            return out
        db.update_cash(cash - cost)
        existing = pos_map.get(ticker)
        if existing and existing["quantity"] > 0:
            new_qty = existing["quantity"] + quantity
            new_avg = (existing["quantity"] * existing["avg_cost"] + quantity * current_price) / new_qty
        else:
            new_qty = quantity
            new_avg = current_price
        db.upsert_position(ticker, new_qty, new_avg)
    else:
        existing = pos_map.get(ticker)
        if not existing or existing["quantity"] < quantity:
            out["status"] = "failed"
            out["error"] = "Insufficient shares"
            return out
        db.update_cash(cash + quantity * current_price)
        db.upsert_position(ticker, existing["quantity"] - quantity, existing["avg_cost"])

    db.record_trade(ticker, side, quantity, current_price)
    portfolio = _build_portfolio()
    db.record_snapshot(portfolio["total_value"])

    out["price"] = current_price
    out["status"] = "executed"
    return out


def _execute_llm_watchlist_change(change: dict) -> dict:
    ticker = change.get("ticker", "").upper()
    action = change.get("action", "")

    out = {"ticker": ticker, "action": action}

    if not ticker or action != "add":
        out["status"] = "failed"
        out["error"] = "Only 'add' action is supported"
        return out

    try:
        db.add_to_watchlist(ticker)
        out["status"] = "executed"
    except ValueError:
        out["status"] = "failed"
        out["error"] = "Ticker already in watchlist"

    return out
