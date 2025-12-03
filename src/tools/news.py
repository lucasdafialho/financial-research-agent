from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from src.config.settings import Settings
from src.core.exceptions import ExternalAPIError
from src.core.types import NewsItem
from src.tools.base import BaseTool


class NewsTool(BaseTool):
    """Tool for fetching financial news from various sources."""

    name = "news"
    description = "Fetches financial news and market updates from news APIs and web sources"

    NEWS_API_URL = "https://newsapi.org/v2"
    GOOGLE_NEWS_URL = "https://news.google.com"

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._news_api_key: str | None = None
        if settings and settings.news_api_key:
            self._news_api_key = settings.news_api_key.get_secret_value()

    async def _execute(self, **kwargs: Any) -> list[NewsItem] | dict[str, Any]:
        """Execute news retrieval."""
        action = kwargs.get("action", "search")
        query = kwargs.get("query")
        tickers = kwargs.get("tickers", [])
        days_back = kwargs.get("days_back", 7)

        if action == "search" and (query or tickers):
            return await self._search_news(query, tickers, days_back)
        elif action == "headlines":
            return await self._get_headlines(kwargs.get("category", "business"))
        elif action == "company_news" and tickers:
            return await self._get_company_news(tickers, days_back)
        else:
            raise ExternalAPIError(
                message="Invalid action or missing parameters",
                service=self.name,
            )

    async def _search_news(
        self,
        query: str | None = None,
        tickers: list[str] | None = None,
        days_back: int = 7,
    ) -> list[NewsItem]:
        """Search for news articles."""
        search_terms = []

        if query:
            search_terms.append(query)

        if tickers:
            for ticker in tickers:
                clean_ticker = ticker.replace(".SA", "").upper()
                search_terms.append(clean_ticker)

        if not search_terms:
            raise ExternalAPIError(
                message="No search terms provided",
                service=self.name,
            )

        results: list[NewsItem] = []

        if self._news_api_key:
            api_results = await self._search_news_api(search_terms, days_back)
            results.extend(api_results)

        google_results = await self._search_google_news(search_terms)
        results.extend(google_results)

        seen_titles: set[str] = set()
        unique_results: list[NewsItem] = []
        for item in results:
            title_normalized = item.title.lower().strip()
            if title_normalized not in seen_titles:
                seen_titles.add(title_normalized)
                unique_results.append(item)

        return sorted(unique_results, key=lambda x: x.published_at, reverse=True)

    async def _search_news_api(
        self,
        search_terms: list[str],
        days_back: int = 7,
    ) -> list[NewsItem]:
        """Search news using NewsAPI."""
        if not self._news_api_key:
            return []

        results: list[NewsItem] = []
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for term in search_terms[:3]:
                try:
                    url = f"{self.NEWS_API_URL}/everything"
                    params = {
                        "q": f"{term} (bolsa OR ações OR mercado OR financeiro)",
                        "from": from_date,
                        "language": "pt",
                        "sortBy": "relevancy",
                        "pageSize": 10,
                        "apiKey": self._news_api_key,
                    }

                    response = await client.get(url, params=params)

                    if response.status_code != 200:
                        self.logger.warning(
                            "news_api_error",
                            status_code=response.status_code,
                            term=term,
                        )
                        continue

                    data = response.json()

                    for article in data.get("articles", []):
                        try:
                            published = article.get("publishedAt", "")
                            if published:
                                published_dt = datetime.fromisoformat(
                                    published.replace("Z", "+00:00")
                                )
                            else:
                                published_dt = datetime.now()

                            results.append(
                                NewsItem(
                                    title=article.get("title", ""),
                                    source=article.get("source", {}).get("name", "Unknown"),
                                    url=article.get("url", ""),
                                    published_at=published_dt,
                                    summary=article.get("description"),
                                    tickers=[
                                        t for t in search_terms if t.upper() in term.upper()
                                    ],
                                )
                            )
                        except Exception as e:
                            self.logger.warning("article_parse_error", error=str(e))
                            continue

                except Exception as e:
                    self.logger.warning("news_api_search_error", term=term, error=str(e))
                    continue

        return results

    async def _search_google_news(
        self,
        search_terms: list[str],
    ) -> list[NewsItem]:
        """Search news using Google News RSS."""
        results: list[NewsItem] = []

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for term in search_terms[:3]:
                try:
                    encoded_query = quote_plus(f"{term} ações Brasil")
                    url = f"{self.GOOGLE_NEWS_URL}/rss/search?q={encoded_query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

                    response = await client.get(url)

                    if response.status_code != 200:
                        continue

                    soup = BeautifulSoup(response.text, "lxml-xml")
                    items = soup.find_all("item")

                    for item in items[:10]:
                        try:
                            title = item.find("title")
                            link = item.find("link")
                            pub_date = item.find("pubDate")
                            source = item.find("source")

                            if not title or not link:
                                continue

                            if pub_date:
                                try:
                                    published_dt = datetime.strptime(
                                        pub_date.text, "%a, %d %b %Y %H:%M:%S %Z"
                                    )
                                except ValueError:
                                    published_dt = datetime.now()
                            else:
                                published_dt = datetime.now()

                            results.append(
                                NewsItem(
                                    title=title.text,
                                    source=source.text if source else "Google News",
                                    url=link.text,
                                    published_at=published_dt,
                                    tickers=[term.upper()] if len(term) <= 6 else [],
                                )
                            )

                        except Exception as e:
                            self.logger.warning("google_news_item_error", error=str(e))
                            continue

                except Exception as e:
                    self.logger.warning("google_news_search_error", term=term, error=str(e))
                    continue

        return results

    async def _get_headlines(self, category: str = "business") -> list[NewsItem]:
        """Get top headlines."""
        results: list[NewsItem] = []

        if self._news_api_key:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                try:
                    url = f"{self.NEWS_API_URL}/top-headlines"
                    params = {
                        "country": "br",
                        "category": category,
                        "pageSize": 20,
                        "apiKey": self._news_api_key,
                    }

                    response = await client.get(url, params=params)

                    if response.status_code == 200:
                        data = response.json()
                        for article in data.get("articles", []):
                            try:
                                published = article.get("publishedAt", "")
                                if published:
                                    published_dt = datetime.fromisoformat(
                                        published.replace("Z", "+00:00")
                                    )
                                else:
                                    published_dt = datetime.now()

                                results.append(
                                    NewsItem(
                                        title=article.get("title", ""),
                                        source=article.get("source", {}).get("name", "Unknown"),
                                        url=article.get("url", ""),
                                        published_at=published_dt,
                                        summary=article.get("description"),
                                    )
                                )
                            except Exception:
                                continue

                except Exception as e:
                    self.logger.warning("headlines_error", error=str(e))

        return results

    async def _get_company_news(
        self,
        tickers: list[str],
        days_back: int = 7,
    ) -> list[NewsItem]:
        """Get news specific to companies."""
        company_mapping = {
            "PETR4": "Petrobras",
            "VALE3": "Vale",
            "ITUB4": "Itaú",
            "BBDC4": "Bradesco",
            "BBAS3": "Banco do Brasil",
            "ABEV3": "Ambev",
            "WEGE3": "WEG",
            "RENT3": "Localiza",
            "LREN3": "Lojas Renner",
            "MGLU3": "Magazine Luiza",
            "B3SA3": "B3",
            "SUZB3": "Suzano",
            "JBSS3": "JBS",
            "GGBR4": "Gerdau",
            "CSNA3": "CSN",
        }

        search_terms = []
        for ticker in tickers:
            clean_ticker = ticker.replace(".SA", "").upper()
            if clean_ticker in company_mapping:
                search_terms.append(company_mapping[clean_ticker])
            search_terms.append(clean_ticker)

        return await self._search_news(
            query=" OR ".join(search_terms[:5]),
            tickers=tickers,
            days_back=days_back,
        )
