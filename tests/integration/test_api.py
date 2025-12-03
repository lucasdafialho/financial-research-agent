import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: AsyncClient) -> None:
        """Test health check endpoint."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_liveness_check(self, async_client: AsyncClient) -> None:
        """Test liveness endpoint."""
        response = await async_client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True

    @pytest.mark.asyncio
    async def test_readiness_check(self, async_client: AsyncClient) -> None:
        """Test readiness endpoint."""
        response = await async_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert "ready" in data


class TestResearchEndpoints:
    """Tests for research endpoints."""

    @pytest.mark.asyncio
    async def test_query_validation_empty(self, async_client: AsyncClient) -> None:
        """Test query validation with empty query."""
        response = await async_client.post(
            "/research/query",
            json={"query": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_validation_too_short(self, async_client: AsyncClient) -> None:
        """Test query validation with too short query."""
        response = await async_client.post(
            "/research/query",
            json={"query": "ab"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_workflow_structure(self, async_client: AsyncClient) -> None:
        """Test workflow structure endpoint."""
        response = await async_client.get("/research/workflow")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data


class TestMarketEndpoints:
    """Tests for market data endpoints."""

    @pytest.mark.asyncio
    async def test_invalid_history_period(self, async_client: AsyncClient) -> None:
        """Test invalid history period."""
        response = await async_client.get("/market/history/PETR4?period=invalid")

        assert response.status_code == 400


class TestDocumentEndpoints:
    """Tests for document endpoints."""

    @pytest.mark.asyncio
    async def test_list_document_types(self, async_client: AsyncClient) -> None:
        """Test listing document types."""
        response = await async_client.get("/documents/types")

        assert response.status_code == 200
        data = response.json()
        assert "types" in data
        assert len(data["types"]) > 0

    @pytest.mark.asyncio
    async def test_upload_non_pdf(self, async_client: AsyncClient) -> None:
        """Test uploading non-PDF file."""
        response = await async_client.post(
            "/documents/upload",
            files={"file": ("test.txt", b"test content", "text/plain")},
            data={
                "company": "Test",
                "ticker": "TEST4",
                "document_type": "quarterly_report",
                "reference_date": "2024-01-01",
            },
        )

        assert response.status_code == 400


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root(self, async_client: AsyncClient) -> None:
        """Test root endpoint."""
        response = await async_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
