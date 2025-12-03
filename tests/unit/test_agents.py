import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.agents.router import RouterAgent
from src.core.types import AgentState, QueryIntent, QueryIntentType, ResearchQuery


class TestRouterAgent:
    """Tests for Router Agent."""

    @pytest.fixture
    def router(self, test_settings) -> RouterAgent:
        return RouterAgent(test_settings)

    def test_extract_tickers_explicit(self, router: RouterAgent) -> None:
        """Test explicit ticker extraction."""
        query = "Análise de PETR4 e VALE3"
        tickers = router._extract_tickers(query)

        assert "PETR4" in tickers
        assert "VALE3" in tickers

    def test_extract_tickers_company_names(self, router: RouterAgent) -> None:
        """Test ticker extraction from company names."""
        query = "Como está a Petrobras?"
        tickers = router._extract_tickers(query)

        assert "PETR4" in tickers or "PETR3" in tickers

    def test_extract_tickers_empty(self, router: RouterAgent) -> None:
        """Test ticker extraction with no tickers."""
        query = "Como funciona o mercado de ações?"
        tickers = router._extract_tickers(query)

        assert len(tickers) == 0

    def test_parse_intent_valid_json(self, router: RouterAgent) -> None:
        """Test parsing valid JSON response."""
        llm_response = """
        {
            "intent_type": "financial_analysis",
            "tickers": ["PETR4"],
            "companies": ["Petrobras"],
            "time_range": "3m",
            "requires_rag": true,
            "requires_market_data": true,
            "requires_news": false,
            "confidence": 0.9
        }
        """

        intent = router._parse_intent(llm_response, ["PETR4"])

        assert intent.intent_type == QueryIntentType.FINANCIAL_ANALYSIS
        assert "PETR4" in intent.tickers
        assert intent.requires_rag is True
        assert intent.confidence == 0.9

    def test_parse_intent_invalid_json(self, router: RouterAgent) -> None:
        """Test parsing invalid JSON returns default intent."""
        llm_response = "Invalid response without JSON"

        intent = router._parse_intent(llm_response, ["PETR4"])

        assert intent.intent_type == QueryIntentType.GENERAL
        assert intent.confidence == 0.5


class TestAgentState:
    """Tests for AgentState operations."""

    def test_agent_state_creation(self) -> None:
        """Test creating agent state."""
        query = ResearchQuery(
            query_id="test-id",
            raw_query="Test query",
        )

        state: AgentState = {
            "query": query,
            "errors": [],
            "metadata": {},
            "completed_agents": [],
        }

        assert state["query"].raw_query == "Test query"
        assert len(state["errors"]) == 0

    def test_agent_state_with_intent(self) -> None:
        """Test agent state with intent."""
        intent = QueryIntent(
            intent_type=QueryIntentType.FINANCIAL_ANALYSIS,
            tickers=["PETR4"],
            requires_rag=True,
            requires_market_data=True,
        )

        state: AgentState = {
            "intent": intent,
            "errors": [],
            "completed_agents": [],
        }

        assert state["intent"].intent_type == QueryIntentType.FINANCIAL_ANALYSIS


class TestQueryIntent:
    """Tests for QueryIntent model."""

    def test_query_intent_defaults(self) -> None:
        """Test default values for QueryIntent."""
        intent = QueryIntent(intent_type=QueryIntentType.GENERAL)

        assert intent.tickers == []
        assert intent.requires_rag is False
        assert intent.requires_market_data is False
        assert intent.confidence == 1.0

    def test_query_intent_with_values(self) -> None:
        """Test QueryIntent with custom values."""
        intent = QueryIntent(
            intent_type=QueryIntentType.COMPARISON,
            tickers=["PETR4", "VALE3"],
            requires_rag=True,
            requires_market_data=True,
            requires_news=True,
            confidence=0.85,
        )

        assert intent.intent_type == QueryIntentType.COMPARISON
        assert len(intent.tickers) == 2
        assert intent.confidence == 0.85
