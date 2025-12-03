from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.responses import MarketDataResponse, NewsItemResponse
from src.tools.news import NewsTool
from src.tools.yahoo_finance import YahooFinanceTool

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get(
    "/quote/{ticker}",
    response_model=MarketDataResponse,
    summary="Get Stock Quote",
    description="Get current quote for a stock ticker",
)
async def get_quote(ticker: str) -> MarketDataResponse:
    """Get current stock quote."""
    tool = YahooFinanceTool()

    result = await tool.execute(action="quote", ticker=ticker)

    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error or f"No data found for ticker {ticker}",
        )

    data = result.data

    return MarketDataResponse(
        ticker=data.ticker,
        company_name=data.company_name,
        current_price=data.current_price,
        change_percent=data.change_percent,
        volume=data.volume,
        market_cap=data.market_cap,
        pe_ratio=data.pe_ratio,
        dividend_yield=data.dividend_yield,
        timestamp=data.timestamp,
        additional_data=data.additional_data,
    )


@router.get(
    "/quotes",
    response_model=list[MarketDataResponse],
    summary="Get Multiple Quotes",
    description="Get quotes for multiple tickers",
)
async def get_quotes(
    tickers: list[str] = Query(..., description="List of tickers"),
) -> list[MarketDataResponse]:
    """Get quotes for multiple tickers."""
    tool = YahooFinanceTool()

    result = await tool.execute(action="quotes", tickers=tickers)

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=result.error or "Failed to fetch quotes",
        )

    return [
        MarketDataResponse(
            ticker=data.ticker,
            company_name=data.company_name,
            current_price=data.current_price,
            change_percent=data.change_percent,
            volume=data.volume,
            market_cap=data.market_cap,
            pe_ratio=data.pe_ratio,
            dividend_yield=data.dividend_yield,
            timestamp=data.timestamp,
            additional_data=data.additional_data,
        )
        for data in result.data
    ]


@router.get(
    "/history/{ticker}",
    summary="Get Price History",
    description="Get historical price data for a ticker",
)
async def get_history(
    ticker: str,
    period: str = Query(default="1mo", description="Period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)"),
) -> dict:
    """Get historical price data."""
    valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]

    if period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Valid options: {valid_periods}",
        )

    tool = YahooFinanceTool()

    result = await tool.execute(action="history", ticker=ticker, period=period)

    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error or f"No history found for ticker {ticker}",
        )

    return result.data


@router.get(
    "/info/{ticker}",
    summary="Get Company Info",
    description="Get detailed company information",
)
async def get_company_info(ticker: str) -> dict:
    """Get comprehensive company information."""
    tool = YahooFinanceTool()

    result = await tool.execute(action="info", ticker=ticker)

    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error or f"No info found for ticker {ticker}",
        )

    return result.data


@router.get(
    "/news",
    response_model=list[NewsItemResponse],
    summary="Get News",
    description="Get financial news",
)
async def get_news(
    query: str | None = Query(default=None, description="Search query"),
    tickers: list[str] | None = Query(default=None, description="Filter by tickers"),
    days_back: int = Query(default=7, ge=1, le=30, description="Days to look back"),
) -> list[NewsItemResponse]:
    """Get financial news."""
    tool = NewsTool()

    result = await tool.execute(
        action="search",
        query=query,
        tickers=tickers or [],
        days_back=days_back,
    )

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=result.error or "Failed to fetch news",
        )

    return [
        NewsItemResponse(
            title=item.title,
            source=item.source,
            url=item.url,
            published_at=item.published_at,
            summary=item.summary,
            tickers=item.tickers,
        )
        for item in result.data
    ]


@router.get(
    "/headlines",
    response_model=list[NewsItemResponse],
    summary="Get Headlines",
    description="Get top business headlines",
)
async def get_headlines() -> list[NewsItemResponse]:
    """Get top business headlines."""
    tool = NewsTool()

    result = await tool.execute(action="headlines", category="business")

    if not result.success:
        return []

    return [
        NewsItemResponse(
            title=item.title,
            source=item.source,
            url=item.url,
            published_at=item.published_at,
            summary=item.summary,
            tickers=item.tickers,
        )
        for item in result.data
    ]
