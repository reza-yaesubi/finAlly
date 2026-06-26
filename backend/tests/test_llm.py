"""Unit tests for the LLM chat integration module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from llm.chat import (
    ERROR_RESPONSE,
    MOCK_RESPONSE,
    SYSTEM_PROMPT_TEMPLATE,
    LLMResponse,
    TradeRequest,
    WatchlistChange,
    _build_messages,
    chat,
)

PORTFOLIO_CONTEXT = {
    "cash": 7500.00,
    "total_value": 10250.00,
    "positions": [
        {
            "ticker": "AAPL",
            "quantity": 10,
            "avg_cost": 190.00,
            "current_price": 192.50,
            "unrealized_pnl": 25.00,
            "pnl_pct": 1.32,
        }
    ],
}


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------


class TestMockMode:
    @pytest.mark.asyncio
    async def test_mock_returns_deterministic_response(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await chat("Hello", PORTFOLIO_CONTEXT, [])
        assert result == MOCK_RESPONSE

    @pytest.mark.asyncio
    async def test_mock_does_not_call_litellm(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        with patch("llm.chat.litellm.completion") as mock_completion:
            await chat("Hello", PORTFOLIO_CONTEXT, [])
            mock_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_mock_false_by_default(self, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        with patch("llm.chat._call_llm") as mock_call:
            mock_call.return_value = LLMResponse(message="ok")
            await chat("Hello", PORTFOLIO_CONTEXT, [])
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_mock_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "TRUE")
        result = await chat("Hello", PORTFOLIO_CONTEXT, [])
        assert result == MOCK_RESPONSE


# ---------------------------------------------------------------------------
# LLMResponse Pydantic model
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_parses_full_valid_json(self):
        raw = json.dumps(
            {
                "message": "Buying AAPL now.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}],
                "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
            }
        )
        result = LLMResponse.model_validate_json(raw)
        assert result.message == "Buying AAPL now."
        assert len(result.trades) == 1
        assert result.trades[0].ticker == "AAPL"
        assert result.trades[0].side == "buy"
        assert result.trades[0].quantity == 5.0
        assert len(result.watchlist_changes) == 1
        assert result.watchlist_changes[0].ticker == "PYPL"
        assert result.watchlist_changes[0].action == "add"

    def test_default_empty_trades(self):
        result = LLMResponse(message="Just a message")
        assert result.trades == []

    def test_default_empty_watchlist_changes(self):
        result = LLMResponse(message="Just a message")
        assert result.watchlist_changes == []

    def test_parses_message_only(self):
        raw = json.dumps({"message": "All good."})
        result = LLMResponse.model_validate_json(raw)
        assert result.message == "All good."
        assert result.trades == []
        assert result.watchlist_changes == []

    def test_fractional_quantity(self):
        raw = json.dumps(
            {
                "message": "Buying 0.5 shares.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 0.5}],
            }
        )
        result = LLMResponse.model_validate_json(raw)
        assert result.trades[0].quantity == 0.5

    def test_trade_request_fields(self):
        trade = TradeRequest(ticker="TSLA", side="sell", quantity=2.0)
        assert trade.ticker == "TSLA"
        assert trade.side == "sell"
        assert trade.quantity == 2.0

    def test_watchlist_change_fields(self):
        change = WatchlistChange(ticker="NVDA", action="add")
        assert change.ticker == "NVDA"
        assert change.action == "add"


# ---------------------------------------------------------------------------
# System prompt includes portfolio context
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_portfolio_json_injected_into_prompt(self):
        messages = _build_messages("Hi", PORTFOLIO_CONTEXT, [])
        system_content = messages[0]["content"]
        portfolio_json = json.dumps(PORTFOLIO_CONTEXT, indent=2)
        assert portfolio_json in system_content

    def test_system_message_role_is_system(self):
        messages = _build_messages("Hi", PORTFOLIO_CONTEXT, [])
        assert messages[0]["role"] == "system"

    def test_user_message_appended_last(self):
        messages = _build_messages("Buy AAPL", PORTFOLIO_CONTEXT, [])
        assert messages[-1] == {"role": "user", "content": "Buy AAPL"}

    def test_history_inserted_between_system_and_user(self):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        messages = _build_messages("Now buy", PORTFOLIO_CONTEXT, history)
        assert messages[0]["role"] == "system"
        assert messages[1] == history[0]
        assert messages[2] == history[1]
        assert messages[-1] == {"role": "user", "content": "Now buy"}

    def test_history_capped_at_20(self):
        history = [{"role": "user", "content": str(i)} for i in range(30)]
        messages = _build_messages("end", PORTFOLIO_CONTEXT, history)
        # system + 20 history + user = 22
        assert len(messages) == 22

    def test_cash_balance_visible_in_prompt(self):
        messages = _build_messages("Hi", PORTFOLIO_CONTEXT, [])
        system_content = messages[0]["content"]
        assert "7500" in system_content

    def test_prompt_mentions_finally_name(self):
        messages = _build_messages("Hi", PORTFOLIO_CONTEXT, [])
        system_content = messages[0]["content"]
        assert "FinAlly" in system_content


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_litellm_exception_returns_error_response(self, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)

        def raise_error(messages):
            raise RuntimeError("network failure")

        with patch("llm.chat._call_llm", side_effect=raise_error):
            result = await chat("Hello", PORTFOLIO_CONTEXT, [])

        assert result == ERROR_RESPONSE

    @pytest.mark.asyncio
    async def test_parse_error_returns_error_response(self, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)

        def bad_response(messages):
            raise ValueError("invalid json")

        with patch("llm.chat._call_llm", side_effect=bad_response):
            result = await chat("Hello", PORTFOLIO_CONTEXT, [])

        assert result == ERROR_RESPONSE

    @pytest.mark.asyncio
    async def test_successful_call_returns_model_dump(self, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)

        expected = LLMResponse(
            message="Done.",
            trades=[TradeRequest(ticker="AAPL", side="buy", quantity=10)],
            watchlist_changes=[],
        )

        with patch("llm.chat._call_llm", return_value=expected):
            result = await chat("Buy 10 AAPL", PORTFOLIO_CONTEXT, [])

        assert result["message"] == "Done."
        assert len(result["trades"]) == 1
        assert result["trades"][0]["ticker"] == "AAPL"
