import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.config.settings import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        app_env="development",
        debug=True,
        secret_key="test-secret-key-for-testing-only",
        database_url="sqlite+aiosqlite:///./test.db",
        redis_url="redis://localhost:6379/1",
        qdrant_host="localhost",
        qdrant_port=6333,
        openai_api_key="test-openai-key",
        llm_provider="openai",
        llm_model="gpt-4",
    )


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='{"summary": "Test summary", "key_findings": [], "risks": []}'
        )
    )
    return mock


@pytest.fixture
def mock_cache() -> MagicMock:
    """Create a mock cache service."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.get_model = AsyncMock(return_value=None)
    mock.set_model = AsyncMock(return_value=True)
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Create a mock vector store service."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[])
    mock.upsert_chunks = AsyncMock(return_value=5)
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def sample_market_data() -> dict[str, Any]:
    """Create sample market data."""
    return {
        "ticker": "PETR4",
        "company_name": "Petrobras",
        "current_price": 35.50,
        "change_percent": 2.5,
        "volume": 50000000,
        "market_cap": 450000000000,
        "pe_ratio": 5.2,
        "dividend_yield": 0.15,
    }


@pytest.fixture
def sample_query_response() -> dict[str, Any]:
    """Create sample query response."""
    return {
        "response_id": "test-response-id",
        "query_id": "test-query-id",
        "content": "# Análise da Petrobras\n\nA empresa apresentou resultados...",
        "format": "markdown",
        "analysis": {
            "summary": "Resultados positivos no trimestre",
            "key_findings": ["Lucro aumentou 15%", "Dívida reduziu"],
            "financial_metrics": {"ebitda": 50000000000},
            "risks": ["Volatilidade do petróleo"],
            "opportunities": ["Expansão internacional"],
            "sentiment": "positivo",
            "confidence_score": 0.85,
        },
        "sources": ["Yahoo Finance", "CVM"],
        "disclaimers": ["Esta análise não constitui recomendação de investimento"],
        "processing_time_ms": 2500,
    }
