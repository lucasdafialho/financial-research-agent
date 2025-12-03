from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW = "cash_flow"
    QUARTERLY_REPORT = "quarterly_report"
    ANNUAL_REPORT = "annual_report"
    EARNINGS_RELEASE = "earnings_release"
    RELEVANT_FACT = "relevant_fact"
    PRESENTATION = "presentation"
    OTHER = "other"


class QueryIntentType(str, Enum):
    FINANCIAL_ANALYSIS = "financial_analysis"
    MARKET_DATA = "market_data"
    NEWS_SENTIMENT = "news_sentiment"
    DOCUMENT_SEARCH = "document_search"
    COMPARISON = "comparison"
    GENERAL = "general"


class MarketData(BaseModel):
    """Market data for a specific ticker."""

    ticker: str
    company_name: str
    current_price: float
    change_percent: float
    volume: int
    market_cap: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    beta: float | None = None
    sector: str | None = None
    industry: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    additional_data: dict[str, Any] = Field(default_factory=dict)


class NewsItem(BaseModel):
    """News article or update."""

    title: str
    source: str
    url: str
    published_at: datetime
    summary: str | None = None
    sentiment_score: float | None = None
    relevance_score: float | None = None
    tickers: list[str] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """Metadata for a financial document."""

    document_id: str
    company: str
    ticker: str
    document_type: DocumentType
    reference_date: datetime
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    source_url: str | None = None
    file_hash: str | None = None
    page_count: int | None = None
    language: str = "pt-BR"


class DocumentChunk(BaseModel):
    """A chunk of text from a document with metadata."""

    chunk_id: str
    document_id: str
    content: str
    page_number: int | None = None
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class QueryIntent(BaseModel):
    """Analyzed intent from user query."""

    intent_type: QueryIntentType
    entities: dict[str, Any] = Field(default_factory=dict)
    tickers: list[str] = Field(default_factory=list)
    time_range: str | None = None
    requires_rag: bool = False
    requires_market_data: bool = False
    requires_news: bool = False
    confidence: float = 1.0


class ResearchQuery(BaseModel):
    """User research query."""

    query_id: str
    raw_query: str
    intent: QueryIntent | None = None
    user_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CollectedData(BaseModel):
    """Data collected by the Collector Agent."""

    market_data: list[MarketData] = Field(default_factory=list)
    news_items: list[NewsItem] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    collection_timestamp: datetime = Field(default_factory=datetime.utcnow)


class RAGContext(BaseModel):
    """Context retrieved by the RAG Agent."""

    chunks: list[DocumentChunk] = Field(default_factory=list)
    total_chunks_found: int = 0
    query_embedding: list[float] | None = None
    search_metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Analysis result from the Analyst Agent."""

    summary: str
    key_findings: list[str] = Field(default_factory=list)
    financial_metrics: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    sentiment: str | None = None
    confidence_score: float = 0.0
    sources_used: list[str] = Field(default_factory=list)


class ResearchResponse(BaseModel):
    """Final response from the Reporter Agent."""

    response_id: str
    query_id: str
    content: str
    format: str = "markdown"
    analysis: AnalysisResult | None = None
    sources: list[str] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    processing_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentState(TypedDict, total=False):
    """Shared state between agents in the workflow."""

    query: ResearchQuery
    intent: QueryIntent
    collected_data: CollectedData
    rag_context: RAGContext
    analysis: AnalysisResult
    response: ResearchResponse
    errors: list[dict[str, Any]]
    metadata: dict[str, Any]
    current_agent: str
    completed_agents: list[str]
