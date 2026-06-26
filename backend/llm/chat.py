"""LLM chat integration for FinAlly.

Calls the LLM via LiteLLM -> OpenRouter (Cerebras inference) and returns
a parsed response dict with message, trades, and watchlist_changes.
"""

import asyncio
import json
import logging
import os

import litellm
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

SYSTEM_PROMPT_TEMPLATE = """You are FinAlly, an AI trading assistant for a simulated trading platform.

You help users:
- Analyze their portfolio composition, risk concentration, and P&L
- Suggest and execute trades (the platform uses virtual money, no real risk)
- Manage the watchlist by adding interesting tickers
- Answer questions about their positions and market activity

Current portfolio context:
{portfolio_json}

Guidelines:
- Be concise and data-driven
- When the user asks you to buy or sell, include the trade in your "trades" field
- When suggesting new tickers to watch, include them in "watchlist_changes"
- Always respond with valid JSON matching the required schema
- Quantities can be fractional (e.g., 0.5 shares)
- You can only ADD tickers to the watchlist, not remove them"""

MOCK_RESPONSE = {
    "message": "Your portfolio is looking healthy. You have $10,000 in cash and no open positions.",
    "trades": [],
    "watchlist_changes": [],
}

ERROR_RESPONSE = {
    "message": "Sorry, I encountered an error processing your request.",
    "trades": [],
    "watchlist_changes": [],
}


class TradeRequest(BaseModel):
    ticker: str
    side: str  # "buy" or "sell"
    quantity: float


class WatchlistChange(BaseModel):
    ticker: str
    action: str  # "add" only


class LLMResponse(BaseModel):
    message: str
    trades: list[TradeRequest] = []
    watchlist_changes: list[WatchlistChange] = []


def _build_messages(message: str, portfolio_context: dict, history: list[dict]) -> list[dict]:
    """Construct the messages list for the LLM call."""
    system_message = {
        "role": "system",
        "content": SYSTEM_PROMPT_TEMPLATE.format(
            portfolio_json=json.dumps(portfolio_context, indent=2)
        ),
    }
    recent_history = history[-20:]
    user_message = {"role": "user", "content": message}
    return [system_message, *recent_history, user_message]


def _call_llm(messages: list[dict]) -> LLMResponse:
    """Synchronous LiteLLM call. Run via asyncio.to_thread."""
    litellm.api_key = os.getenv("OPENROUTER_API_KEY")
    response = litellm.completion(
        model=MODEL,
        messages=messages,
        response_format=LLMResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    raw = response.choices[0].message.content
    return LLMResponse.model_validate_json(raw)


async def chat(
    message: str,
    portfolio_context: dict,
    history: list[dict],
) -> dict:
    """Call the LLM and return a parsed response dict.

    Args:
        message: The user's current message.
        portfolio_context: Current portfolio state (cash, positions, etc.).
        history: Last N chat messages as [{"role": ..., "content": ...}].

    Returns:
        Dict with keys: message, trades, watchlist_changes.
    """
    if os.getenv("LLM_MOCK", "false").lower() == "true":
        return MOCK_RESPONSE

    messages = _build_messages(message, portfolio_context, history)
    try:
        result = await asyncio.to_thread(_call_llm, messages)
        return result.model_dump()
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return ERROR_RESPONSE
