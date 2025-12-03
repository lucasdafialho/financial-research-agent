from datetime import datetime

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request schema for research queries."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The research query to process",
        examples=["Qual a situação financeira da Petrobras no último trimestre?"],
    )
    user_id: str | None = Field(
        default=None,
        description="Optional user identifier for tracking",
    )
    options: dict | None = Field(
        default=None,
        description="Optional query options",
    )


class DocumentUploadRequest(BaseModel):
    """Request schema for document upload metadata."""

    company: str = Field(..., min_length=1, max_length=255)
    ticker: str = Field(..., min_length=4, max_length=10)
    document_type: str = Field(
        ...,
        description="Type of document (quarterly_report, annual_report, etc.)",
    )
    reference_date: datetime = Field(
        ...,
        description="Reference date for the document",
    )
    source_url: str | None = Field(
        default=None,
        description="Original source URL if available",
    )


class MarketDataRequest(BaseModel):
    """Request schema for market data queries."""

    tickers: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of stock tickers",
    )
    include_history: bool = Field(
        default=False,
        description="Include historical data",
    )
    period: str = Field(
        default="1mo",
        description="Historical data period",
    )


class NewsSearchRequest(BaseModel):
    """Request schema for news search."""

    query: str | None = Field(
        default=None,
        description="Search query",
    )
    tickers: list[str] | None = Field(
        default=None,
        description="Filter by tickers",
    )
    days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to look back",
    )
