from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: dict[str, bool] = Field(
        default_factory=dict,
        description="Health status of individual components",
    )


class ErrorResponse(BaseModel):
    """Response schema for errors."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )
    request_id: str | None = Field(
        default=None,
        description="Request ID for tracking",
    )


class AnalysisResultResponse(BaseModel):
    """Response schema for analysis results."""

    summary: str
    key_findings: list[str]
    financial_metrics: dict[str, Any]
    risks: list[str]
    opportunities: list[str]
    sentiment: str | None
    confidence_score: float


class QueryResponse(BaseModel):
    """Response schema for research queries."""

    response_id: str = Field(..., description="Unique response identifier")
    query_id: str = Field(..., description="Original query identifier")
    content: str = Field(..., description="Response content")
    format: str = Field(default="markdown", description="Response format")
    analysis: AnalysisResultResponse | None = Field(
        default=None,
        description="Detailed analysis if available",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Sources used in the response",
    )
    disclaimers: list[str] = Field(
        default_factory=list,
        description="Legal disclaimers",
    )
    processing_time_ms: float = Field(
        default=0.0,
        description="Processing time in milliseconds",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DocumentResponse(BaseModel):
    """Response schema for document operations."""

    document_id: str
    company: str
    ticker: str
    document_type: str
    reference_date: datetime
    chunks_created: int
    status: str
    message: str | None = None


class MarketDataResponse(BaseModel):
    """Response schema for market data."""

    ticker: str
    company_name: str
    current_price: float
    change_percent: float
    volume: int
    market_cap: float | None
    pe_ratio: float | None
    dividend_yield: float | None
    timestamp: datetime
    additional_data: dict[str, Any] = Field(default_factory=dict)


class NewsItemResponse(BaseModel):
    """Response schema for news items."""

    title: str
    source: str
    url: str
    published_at: datetime
    summary: str | None
    tickers: list[str]


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool
