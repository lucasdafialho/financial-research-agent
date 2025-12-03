import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.yahoo_finance import YahooFinanceTool
from src.tools.base import ToolResult
from src.core.types import MarketData


class TestYahooFinanceTool:
    """Tests for Yahoo Finance tool."""

    @pytest.fixture
    def tool(self) -> YahooFinanceTool:
        return YahooFinanceTool()

    def test_normalize_ticker_adds_suffix(self, tool: YahooFinanceTool) -> None:
        """Test that Brazilian suffix is added to tickers."""
        assert tool._normalize_ticker("PETR4") == "PETR4.SA"
        assert tool._normalize_ticker("petr4") == "PETR4.SA"

    def test_normalize_ticker_preserves_existing_suffix(
        self, tool: YahooFinanceTool
    ) -> None:
        """Test that existing suffixes are preserved."""
        assert tool._normalize_ticker("AAPL") == "AAPL.SA"

    @pytest.mark.asyncio
    async def test_get_quote_success(self, tool: YahooFinanceTool) -> None:
        """Test successful quote retrieval."""
        mock_info = {
            "longName": "Petrobras",
            "regularMarketPrice": 35.50,
            "regularMarketChangePercent": 2.5,
            "regularMarketVolume": 50000000,
            "marketCap": 450000000000,
            "trailingPE": 5.2,
            "dividendYield": 0.15,
        }

        with patch.object(tool, "_get_quote") as mock_get:
            mock_get.return_value = MarketData(
                ticker="PETR4",
                company_name="Petrobras",
                current_price=35.50,
                change_percent=2.5,
                volume=50000000,
                market_cap=450000000000,
            )

            result = await tool.execute(action="quote", ticker="PETR4")

            assert result.success
            assert result.data.ticker == "PETR4"

    @pytest.mark.asyncio
    async def test_execute_invalid_action(self, tool: YahooFinanceTool) -> None:
        """Test that invalid action returns error."""
        result = await tool.execute(action="invalid_action")

        assert not result.success
        assert "Invalid action" in (result.error or "")


class TestToolResult:
    """Tests for ToolResult model."""

    def test_tool_result_success(self) -> None:
        """Test successful tool result."""
        result = ToolResult(
            success=True,
            data={"test": "data"},
            execution_time_ms=100.5,
            source="test_tool",
        )

        assert result.success
        assert result.data == {"test": "data"}
        assert result.error is None

    def test_tool_result_failure(self) -> None:
        """Test failed tool result."""
        result = ToolResult(
            success=False,
            error="Test error message",
            execution_time_ms=50.0,
            source="test_tool",
        )

        assert not result.success
        assert result.error == "Test error message"
        assert result.data is None
