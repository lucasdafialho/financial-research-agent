import json
import re
from typing import Any

from src.agents.base import BaseAgent
from src.config.settings import Settings
from src.core.types import AgentState, AnalysisResult, QueryIntentType
from src.rag.retriever import RAGRetriever


class AnalystAgent(BaseAgent):
    """Agent responsible for analyzing collected data and generating insights."""

    name = "analyst"
    description = "Analyzes financial data and documents to generate actionable insights"

    def __init__(
        self,
        settings: Settings,
        retriever: RAGRetriever | None = None,
    ) -> None:
        super().__init__(settings)
        self._retriever = retriever

    @property
    def system_prompt(self) -> str:
        return """Você é um analista financeiro especializado no mercado brasileiro.
Sua função é analisar dados financeiros de forma objetiva e fundamentada.

Diretrizes:
1. Baseie suas análises exclusivamente nos dados fornecidos
2. Seja objetivo e evite especulações
3. Destaque tanto pontos positivos quanto riscos
4. Use métricas e números específicos quando disponíveis
5. Compare com benchmarks do setor quando relevante
6. Identifique tendências e padrões

Formato de resposta esperado (JSON):
{
    "summary": "Resumo executivo da análise",
    "key_findings": ["Achado 1", "Achado 2", ...],
    "financial_metrics": {
        "metric_name": value,
        ...
    },
    "risks": ["Risco 1", "Risco 2", ...],
    "opportunities": ["Oportunidade 1", ...],
    "sentiment": "positivo|neutro|negativo",
    "confidence_score": 0.0-1.0
}

Não faça recomendações de investimento. Foque em análise factual."""

    async def execute(self, state: AgentState) -> AgentState:
        """Analyze collected data and generate insights."""
        query = state.get("query")
        intent = state.get("intent")
        collected_data = state.get("collected_data")
        rag_context = state.get("rag_context")

        if not query:
            return self.add_error(state, ValueError("Query required"))

        analysis_context = self._build_analysis_context(
            query.raw_query,
            intent,
            collected_data,
            rag_context,
        )

        try:
            llm_response = await self.invoke_llm(
                user_message=analysis_context,
            )

            analysis = self._parse_analysis(llm_response)
            analysis.sources_used = self._get_sources(collected_data, rag_context)

            self.logger.info(
                "analysis_complete",
                sentiment=analysis.sentiment,
                findings_count=len(analysis.key_findings),
                risks_count=len(analysis.risks),
                confidence=analysis.confidence_score,
            )

            return self.update_state(state, {"analysis": analysis})

        except Exception as e:
            self.logger.exception("analysis_error", error=str(e))
            return self.add_error(state, e)

    def _build_analysis_context(
        self,
        raw_query: str,
        intent: Any,
        collected_data: Any,
        rag_context: Any,
    ) -> str:
        """Build context string for analysis."""
        parts = [f"## Consulta do Usuário\n{raw_query}\n"]

        if intent:
            parts.append(f"## Tipo de Análise\n{intent.intent_type.value}\n")
            if intent.tickers:
                parts.append(f"Tickers: {', '.join(intent.tickers)}\n")

        if collected_data:
            if collected_data.market_data:
                parts.append("## Dados de Mercado\n")
                for md in collected_data.market_data:
                    parts.append(f"""
**{md.ticker} - {md.company_name}**
- Preço Atual: R$ {md.current_price:.2f}
- Variação: {md.change_percent:.2f}%
- Volume: {md.volume:,}
- Market Cap: R$ {md.market_cap:,.0f if md.market_cap else 'N/A'}
- P/E: {md.pe_ratio:.2f if md.pe_ratio else 'N/A'}
- Dividend Yield: {md.dividend_yield * 100:.2f}% if md.dividend_yield else 'N/A'
""")

            if collected_data.news_items:
                parts.append("\n## Notícias Recentes\n")
                for news in collected_data.news_items[:5]:
                    parts.append(f"- **{news.title}** ({news.source}, {news.published_at.strftime('%d/%m/%Y')})\n")

            if collected_data.raw_data.get("cvm"):
                parts.append("\n## Documentos CVM Disponíveis\n")
                for doc in collected_data.raw_data["cvm"][:5]:
                    parts.append(f"- {doc.get('document_type', 'N/A')} - {doc.get('year', 'N/A')}\n")

        if rag_context and rag_context.chunks:
            parts.append("\n## Informações de Documentos\n")
            if self._retriever:
                formatted = self._retriever.format_context(rag_context, max_tokens=3000)
                parts.append(formatted)
            else:
                for i, chunk in enumerate(rag_context.chunks[:5]):
                    parts.append(f"\n[Documento {i + 1}]\n{chunk.content[:500]}...\n")

        parts.append("""
## Instruções
Com base nas informações acima, forneça uma análise financeira completa em formato JSON.
Inclua todos os campos solicitados no formato de resposta.""")

        return "\n".join(parts)

    def _parse_analysis(self, llm_response: str) -> AnalysisResult:
        """Parse LLM response into AnalysisResult."""
        try:
            json_match = re.search(r"\{[\s\S]*\}", llm_response)
            if json_match:
                data = json.loads(json_match.group())

                return AnalysisResult(
                    summary=data.get("summary", "Análise não disponível"),
                    key_findings=data.get("key_findings", []),
                    financial_metrics=data.get("financial_metrics", {}),
                    risks=data.get("risks", []),
                    opportunities=data.get("opportunities", []),
                    sentiment=data.get("sentiment", "neutro"),
                    confidence_score=data.get("confidence_score", 0.7),
                )

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning("analysis_parse_error", error=str(e))

        return AnalysisResult(
            summary=llm_response[:500] if llm_response else "Análise não disponível",
            key_findings=[],
            financial_metrics={},
            risks=[],
            opportunities=[],
            sentiment="neutro",
            confidence_score=0.5,
        )

    def _get_sources(
        self,
        collected_data: Any,
        rag_context: Any,
    ) -> list[str]:
        """Get list of sources used in analysis."""
        sources: list[str] = []

        if collected_data:
            sources.extend(collected_data.sources)

        if rag_context and rag_context.chunks:
            for chunk in rag_context.chunks:
                if chunk.metadata.get("company"):
                    source = f"{chunk.metadata['company']} - {chunk.metadata.get('document_type', 'Documento')}"
                    if source not in sources:
                        sources.append(source)

        return sources
