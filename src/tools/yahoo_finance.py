from datetime import datetime, timedelta
from typing import Any

import yfinance as yf

from src.core.exceptions import ExternalAPIError
from src.core.types import MarketData
from src.tools.base import BaseTool


class YahooFinanceTool(BaseTool):
    """Tool for fetching financial data from Yahoo Finance."""

    name = "yahoo_finance"
    description = "Fetches stock quotes, historical data, and fundamental indicators from Yahoo Finance"

    BRAZILIAN_SUFFIX = ".SA"

    def _normalize_ticker(self, ticker: str) -> str:
        """Normalize ticker to Yahoo Finance format."""
        ticker = ticker.upper().strip()
        if not ticker.endswith(self.BRAZILIAN_SUFFIX) and not any(
            c in ticker for c in [".", "^", "="]
        ):
            ticker = f"{ticker}{self.BRAZILIAN_SUFFIX}"
        return ticker

    async def _execute(self, **kwargs: Any) -> MarketData | list[MarketData] | dict[str, Any]:
        """Execute Yahoo Finance data retrieval."""
        action = kwargs.get("action", "quote")
        ticker = kwargs.get("ticker")
        tickers = kwargs.get("tickers", [])

        if action == "quote" and ticker:
            return await self._get_quote(ticker)
        elif action == "quotes" and tickers:
            return await self._get_multiple_quotes(tickers)
        elif action == "history" and ticker:
            period = kwargs.get("period", "1mo")
            return await self._get_history(ticker, period)
        elif action == "info" and ticker:
            return await self._get_full_info(ticker)
        else:
            raise ExternalAPIError(
                message="Invalid action or missing parameters",
                service=self.name,
            )

    async def _get_quote(self, ticker: str) -> MarketData:
        """Get current quote for a single ticker."""
        normalized_ticker = self._normalize_ticker(ticker)

        try:
            stock = yf.Ticker(normalized_ticker)
            info = stock.info

            if not info or "regularMarketPrice" not in info:
                raise ExternalAPIError(
                    message=f"No data found for ticker {ticker}",
                    service=self.name,
                )

            return MarketData(
                ticker=ticker.upper(),
                company_name=info.get("longName", info.get("shortName", ticker)),
                current_price=info.get("regularMarketPrice", 0.0),
                change_percent=info.get("regularMarketChangePercent", 0.0),
                volume=info.get("regularMarketVolume", 0),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                dividend_yield=info.get("dividendYield"),
                fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
                fifty_two_week_low=info.get("fiftyTwoWeekLow"),
                beta=info.get("beta"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                additional_data={
                    "currency": info.get("currency", "BRL"),
                    "exchange": info.get("exchange"),
                    "previous_close": info.get("previousClose"),
                    "open": info.get("regularMarketOpen"),
                    "day_high": info.get("dayHigh"),
                    "day_low": info.get("dayLow"),
                    "avg_volume": info.get("averageVolume"),
                    "book_value": info.get("bookValue"),
                    "price_to_book": info.get("priceToBook"),
                    "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
                    "profit_margins": info.get("profitMargins"),
                    "revenue_growth": info.get("revenueGrowth"),
                },
            )

        except Exception as e:
            if "No data found" in str(e):
                raise
            raise ExternalAPIError(
                message=f"Failed to fetch quote for {ticker}: {str(e)}",
                service=self.name,
            )

    async def _get_multiple_quotes(self, tickers: list[str]) -> list[MarketData]:
        """Get quotes for multiple tickers."""
        results: list[MarketData] = []
        for ticker in tickers:
            try:
                quote = await self._get_quote(ticker)
                results.append(quote)
            except ExternalAPIError:
                self.logger.warning("quote_fetch_failed", ticker=ticker)
                continue
        return results

    async def _get_history(
        self,
        ticker: str,
        period: str = "1mo",
    ) -> dict[str, Any]:
        """Get historical price data."""
        normalized_ticker = self._normalize_ticker(ticker)

        try:
            stock = yf.Ticker(normalized_ticker)
            hist = stock.history(period=period)

            if hist.empty:
                raise ExternalAPIError(
                    message=f"No historical data found for {ticker}",
                    service=self.name,
                )

            return {
                "ticker": ticker.upper(),
                "period": period,
                "data": [
                    {
                        "date": index.strftime("%Y-%m-%d"),
                        "open": row["Open"],
                        "high": row["High"],
                        "low": row["Low"],
                        "close": row["Close"],
                        "volume": int(row["Volume"]),
                    }
                    for index, row in hist.iterrows()
                ],
                "statistics": {
                    "min_price": float(hist["Low"].min()),
                    "max_price": float(hist["High"].max()),
                    "avg_price": float(hist["Close"].mean()),
                    "total_volume": int(hist["Volume"].sum()),
                    "price_change": float(hist["Close"].iloc[-1] - hist["Close"].iloc[0]),
                    "price_change_percent": float(
                        ((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0])
                        * 100
                    ),
                },
            }

        except Exception as e:
            if "No historical data" in str(e):
                raise
            raise ExternalAPIError(
                message=f"Failed to fetch history for {ticker}: {str(e)}",
                service=self.name,
            )

    async def _get_full_info(self, ticker: str) -> dict[str, Any]:
        """Get comprehensive company information."""
        normalized_ticker = self._normalize_ticker(ticker)

        try:
            stock = yf.Ticker(normalized_ticker)
            info = stock.info

            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            dividends = stock.dividends
            dividends_year = dividends[dividends.index >= start_date.strftime("%Y-%m-%d")]

            return {
                "ticker": ticker.upper(),
                "basic_info": {
                    "name": info.get("longName"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "country": info.get("country"),
                    "website": info.get("website"),
                    "employees": info.get("fullTimeEmployees"),
                    "description": info.get("longBusinessSummary"),
                },
                "market_data": {
                    "price": info.get("regularMarketPrice"),
                    "market_cap": info.get("marketCap"),
                    "enterprise_value": info.get("enterpriseValue"),
                    "volume": info.get("regularMarketVolume"),
                    "avg_volume_10d": info.get("averageVolume10days"),
                    "shares_outstanding": info.get("sharesOutstanding"),
                    "float_shares": info.get("floatShares"),
                },
                "valuation": {
                    "pe_ratio": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "peg_ratio": info.get("pegRatio"),
                    "price_to_book": info.get("priceToBook"),
                    "price_to_sales": info.get("priceToSalesTrailing12Months"),
                    "ev_to_revenue": info.get("enterpriseToRevenue"),
                    "ev_to_ebitda": info.get("enterpriseToEbitda"),
                },
                "financials": {
                    "revenue": info.get("totalRevenue"),
                    "revenue_growth": info.get("revenueGrowth"),
                    "gross_profit": info.get("grossProfits"),
                    "gross_margins": info.get("grossMargins"),
                    "operating_margins": info.get("operatingMargins"),
                    "profit_margins": info.get("profitMargins"),
                    "ebitda": info.get("ebitda"),
                    "net_income": info.get("netIncomeToCommon"),
                    "eps": info.get("trailingEps"),
                    "forward_eps": info.get("forwardEps"),
                },
                "balance_sheet": {
                    "total_cash": info.get("totalCash"),
                    "total_debt": info.get("totalDebt"),
                    "debt_to_equity": info.get("debtToEquity"),
                    "current_ratio": info.get("currentRatio"),
                    "quick_ratio": info.get("quickRatio"),
                    "book_value": info.get("bookValue"),
                },
                "dividends": {
                    "dividend_rate": info.get("dividendRate"),
                    "dividend_yield": info.get("dividendYield"),
                    "payout_ratio": info.get("payoutRatio"),
                    "ex_dividend_date": info.get("exDividendDate"),
                    "last_dividends": [
                        {"date": d.strftime("%Y-%m-%d"), "amount": float(v)}
                        for d, v in dividends_year.items()
                    ]
                    if not dividends_year.empty
                    else [],
                },
                "risk_metrics": {
                    "beta": info.get("beta"),
                    "52_week_high": info.get("fiftyTwoWeekHigh"),
                    "52_week_low": info.get("fiftyTwoWeekLow"),
                    "50_day_avg": info.get("fiftyDayAverage"),
                    "200_day_avg": info.get("twoHundredDayAverage"),
                },
            }

        except Exception as e:
            raise ExternalAPIError(
                message=f"Failed to fetch info for {ticker}: {str(e)}",
                service=self.name,
            )
