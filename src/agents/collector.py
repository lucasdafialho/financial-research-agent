import asyncio
from datetime import datetime

from src.agents.base import BaseAgent
from src.config.settings import Settings
from src.core.types import AgentState, CollectedData, MarketData, NewsItem
from src.infrastructure.cache import CacheService
from src.tools.cvm import CVMTool
from src.tools.news import NewsTool
from src.tools.yahoo_finance import YahooFinanceTool


class CollectorAgent(BaseAgent):
    """Agent responsible for collecting data from external sources."""

    name = "collector"
    description = "Collects market data, news, and regulatory documents from external sources"

    def __init__(
        self,
        settings: Settings,
        cache_service: CacheService | None = None,
    ) -> None:
        super().__init__(settings)
        self._cache = cache_service
        self._yahoo_tool = YahooFinanceTool()
        self._cvm_tool = CVMTool()
        self._news_tool = NewsTool(settings)

    @property
    def system_prompt(self) -> str:
        return """Você é um agente coletor de dados financeiros.
Sua função é reunir dados de múltiplas fontes de forma eficiente e estruturada.
Você não analisa os dados, apenas coleta e organiza."""

    async def execute(self, state: AgentState) -> AgentState:
        """Collect data based on query intent."""
        intent = state.get("intent")
        if not intent:
            return self.add_error(state, ValueError("No intent provided"))

        tickers = intent.tickers
        collected_data = CollectedData(
            sources=[],
            collection_timestamp=datetime.utcnow(),
        )

        tasks = []

        if intent.requires_market_data and tickers:
            tasks.append(self._collect_market_data(tickers))

        if intent.requires_news and tickers:
            tasks.append(self._collect_news(tickers))

        if tickers:
            tasks.append(self._collect_cvm_info(tickers))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    self.logger.warning("collection_task_error", error=str(result))
                    continue

                if isinstance(result, dict):
                    if "market_data" in result:
                        collected_data.market_data.extend(result["market_data"])
                        collected_data.sources.append("yahoo_finance")
                    if "news_items" in result:
                        collected_data.news_items.extend(result["news_items"])
                        collected_data.sources.append("news")
                    if "cvm_data" in result:
                        collected_data.raw_data["cvm"] = result["cvm_data"]
                        collected_data.sources.append("cvm")

        self.logger.info(
            "data_collected",
            market_data_count=len(collected_data.market_data),
            news_count=len(collected_data.news_items),
            sources=collected_data.sources,
        )

        return self.update_state(state, {"collected_data": collected_data})

    async def _collect_market_data(
        self,
        tickers: list[str],
    ) -> dict[str, list[MarketData]]:
        """Collect market data for tickers."""
        market_data: list[MarketData] = []

        for ticker in tickers:
            cache_key = None
            if self._cache:
                cache_key = CacheService.generate_key("quote", ticker)
                cached = await self._cache.get_model(cache_key, MarketData)
                if cached:
                    market_data.append(cached)
                    continue

            result = await self._yahoo_tool.execute(action="quote", ticker=ticker)

            if result.success and result.data:
                data = result.data
                if isinstance(data, MarketData):
                    market_data.append(data)
                    if self._cache and cache_key:
                        await self._cache.set_model(cache_key, data, ttl=300)

        return {"market_data": market_data}

    async def _collect_news(
        self,
        tickers: list[str],
    ) -> dict[str, list[NewsItem]]:
        """Collect news for tickers."""
        result = await self._news_tool.execute(
            action="company_news",
            tickers=tickers,
            days_back=7,
        )

        if result.success and result.data:
            return {"news_items": result.data}

        return {"news_items": []}

    async def _collect_cvm_info(
        self,
        tickers: list[str],
    ) -> dict[str, list[dict]]:
        """Collect CVM regulatory information."""
        cvm_data: list[dict] = []

        for ticker in tickers:
            result = await self._cvm_tool.execute(
                action="list_filings",
                ticker=ticker,
            )

            if result.success and result.data:
                cvm_data.extend(result.data)

        return {"cvm_data": cvm_data}

    async def collect_detailed_info(
        self,
        ticker: str,
    ) -> dict:
        """Collect detailed information for a single ticker."""
        result = await self._yahoo_tool.execute(action="info", ticker=ticker)

        if result.success and result.data:
            return result.data

        return {}

    async def collect_historical_data(
        self,
        ticker: str,
        period: str = "1mo",
    ) -> dict:
        """Collect historical price data."""
        result = await self._yahoo_tool.execute(
            action="history",
            ticker=ticker,
            period=period,
        )

        if result.success and result.data:
            return result.data

        return {}
