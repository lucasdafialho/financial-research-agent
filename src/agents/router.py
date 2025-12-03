import json
import re

from src.agents.base import BaseAgent
from src.config.settings import Settings
from src.core.types import AgentState, QueryIntent, QueryIntentType


class RouterAgent(BaseAgent):
    """Agent responsible for analyzing queries and routing to appropriate agents."""

    name = "router"
    description = "Analyzes user queries and determines which agents to invoke"

    TICKER_PATTERN = re.compile(r"\b([A-Z]{4}[0-9]{1,2})\b")
    COMPANY_PATTERNS = {
        "petrobras": ["PETR4", "PETR3"],
        "vale": ["VALE3"],
        "itau": ["ITUB4", "ITUB3"],
        "itaú": ["ITUB4", "ITUB3"],
        "bradesco": ["BBDC4", "BBDC3"],
        "banco do brasil": ["BBAS3"],
        "ambev": ["ABEV3"],
        "weg": ["WEGE3"],
        "localiza": ["RENT3"],
        "renner": ["LREN3"],
        "magazine luiza": ["MGLU3"],
        "magalu": ["MGLU3"],
        "b3": ["B3SA3"],
        "suzano": ["SUZB3"],
        "jbs": ["JBSS3"],
        "gerdau": ["GGBR4"],
        "csn": ["CSNA3"],
    }

    @property
    def system_prompt(self) -> str:
        return """Você é um assistente especializado em análise de consultas financeiras.
Sua tarefa é analisar a pergunta do usuário e determinar:
1. O tipo de intenção da consulta
2. Quais empresas/tickers estão sendo mencionados
3. Qual período de tempo é relevante
4. Quais fontes de dados são necessárias

Retorne sua análise em formato JSON com a seguinte estrutura:
{
    "intent_type": "financial_analysis|market_data|news_sentiment|document_search|comparison|general",
    "tickers": ["TICKER1", "TICKER2"],
    "companies": ["Nome da Empresa"],
    "time_range": "current|1d|1w|1m|3m|6m|1y|ytd|specific_date",
    "requires_rag": true/false,
    "requires_market_data": true/false,
    "requires_news": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Explicação breve do racionínio"
}

Regras:
- financial_analysis: Perguntas sobre situação financeira, balanços, resultados
- market_data: Perguntas sobre cotações, preços, variações
- news_sentiment: Perguntas sobre notícias, sentimento de mercado
- document_search: Busca específica em documentos regulatórios
- comparison: Comparações entre empresas ou períodos
- general: Perguntas gerais sobre o mercado

requires_rag deve ser true se a pergunta requer informações de documentos como balanços, relatórios trimestrais, fatos relevantes.
requires_market_data deve ser true se a pergunta envolve cotações, preços, indicadores de mercado.
requires_news deve ser true se a pergunta envolve notícias recentes ou sentimento."""

    async def execute(self, state: AgentState) -> AgentState:
        """Analyze query and determine routing."""
        query = state.get("query")
        if not query:
            return self.add_error(state, ValueError("No query provided"))

        raw_query = query.raw_query

        extracted_tickers = self._extract_tickers(raw_query)

        try:
            llm_response = await self.invoke_llm(
                f"Analise a seguinte consulta financeira:\n\n{raw_query}"
            )

            intent = self._parse_intent(llm_response, extracted_tickers)

            self.logger.info(
                "query_analyzed",
                intent_type=intent.intent_type.value,
                tickers=intent.tickers,
                requires_rag=intent.requires_rag,
                requires_market_data=intent.requires_market_data,
                requires_news=intent.requires_news,
            )

            return self.update_state(state, {"intent": intent})

        except Exception as e:
            self.logger.exception("router_error", error=str(e))

            default_intent = QueryIntent(
                intent_type=QueryIntentType.GENERAL,
                tickers=extracted_tickers,
                requires_rag=True,
                requires_market_data=True,
                requires_news=True,
                confidence=0.5,
            )

            return self.update_state(state, {"intent": default_intent})

    def _extract_tickers(self, query: str) -> list[str]:
        """Extract stock tickers from query."""
        tickers: list[str] = []

        explicit_tickers = self.TICKER_PATTERN.findall(query.upper())
        tickers.extend(explicit_tickers)

        query_lower = query.lower()
        for company, company_tickers in self.COMPANY_PATTERNS.items():
            if company in query_lower:
                tickers.extend(company_tickers)

        return list(set(tickers))

    def _parse_intent(
        self,
        llm_response: str,
        extracted_tickers: list[str],
    ) -> QueryIntent:
        """Parse LLM response into QueryIntent."""
        try:
            json_match = re.search(r"\{[\s\S]*\}", llm_response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            intent_type_str = data.get("intent_type", "general")
            intent_type_map = {
                "financial_analysis": QueryIntentType.FINANCIAL_ANALYSIS,
                "market_data": QueryIntentType.MARKET_DATA,
                "news_sentiment": QueryIntentType.NEWS_SENTIMENT,
                "document_search": QueryIntentType.DOCUMENT_SEARCH,
                "comparison": QueryIntentType.COMPARISON,
                "general": QueryIntentType.GENERAL,
            }
            intent_type = intent_type_map.get(intent_type_str, QueryIntentType.GENERAL)

            llm_tickers = data.get("tickers", [])
            all_tickers = list(set(extracted_tickers + llm_tickers))

            return QueryIntent(
                intent_type=intent_type,
                entities={
                    "companies": data.get("companies", []),
                    "reasoning": data.get("reasoning", ""),
                },
                tickers=all_tickers,
                time_range=data.get("time_range"),
                requires_rag=data.get("requires_rag", True),
                requires_market_data=data.get("requires_market_data", True),
                requires_news=data.get("requires_news", False),
                confidence=data.get("confidence", 0.8),
            )

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning("intent_parse_error", error=str(e))

            return QueryIntent(
                intent_type=QueryIntentType.GENERAL,
                tickers=extracted_tickers,
                requires_rag=True,
                requires_market_data=True,
                requires_news=True,
                confidence=0.5,
            )
