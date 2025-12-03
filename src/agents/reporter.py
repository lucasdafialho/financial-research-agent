from datetime import datetime
from uuid import uuid4

from src.agents.base import BaseAgent
from src.config.settings import Settings
from src.core.types import AgentState, AnalysisResult, ResearchResponse


class ReporterAgent(BaseAgent):
    """Agent responsible for synthesizing analysis into final response."""

    name = "reporter"
    description = "Synthesizes analysis results into coherent, formatted responses"

    DISCLAIMERS = [
        "Esta análise é apenas informativa e não constitui recomendação de investimento.",
        "Resultados passados não garantem resultados futuros.",
        "Consulte um profissional qualificado antes de tomar decisões de investimento.",
    ]

    @property
    def system_prompt(self) -> str:
        return """Você é um redator especializado em relatórios financeiros.
Sua função é transformar análises técnicas em textos claros e acessíveis.

Diretrizes:
1. Use linguagem clara e profissional
2. Estruture a resposta de forma lógica
3. Destaque os pontos mais importantes
4. Inclua dados numéricos quando relevantes
5. Seja conciso mas completo
6. Adapte o tom ao contexto da pergunta

Formatos disponíveis:
- markdown: Formatação rica com títulos, listas e destaques
- plain: Texto simples sem formatação
- executive: Resumo executivo curto e direto

Sempre inclua:
- Resposta direta à pergunta
- Principais insights
- Contexto relevante
- Fontes utilizadas"""

    async def execute(self, state: AgentState) -> AgentState:
        """Generate final response from analysis."""
        query = state.get("query")
        analysis = state.get("analysis")

        if not query:
            return self.add_error(state, ValueError("Query required"))

        response_format = self._determine_format(query.raw_query)

        try:
            if analysis:
                content = await self._generate_response(
                    query.raw_query,
                    analysis,
                    response_format,
                )
            else:
                content = self._generate_fallback_response(query.raw_query, state)

            response = ResearchResponse(
                response_id=str(uuid4()),
                query_id=query.query_id,
                content=content,
                format=response_format,
                analysis=analysis,
                sources=analysis.sources_used if analysis else [],
                disclaimers=self.DISCLAIMERS,
                timestamp=datetime.utcnow(),
            )

            self.logger.info(
                "response_generated",
                response_id=response.response_id,
                format=response_format,
                content_length=len(content),
            )

            return self.update_state(state, {"response": response})

        except Exception as e:
            self.logger.exception("reporter_error", error=str(e))
            return self.add_error(state, e)

    def _determine_format(self, query: str) -> str:
        """Determine response format based on query."""
        query_lower = query.lower()

        if any(term in query_lower for term in ["resumo", "breve", "rápido", "executive"]):
            return "executive"
        elif any(term in query_lower for term in ["detalhado", "completo", "análise"]):
            return "markdown"
        else:
            return "markdown"

    async def _generate_response(
        self,
        query: str,
        analysis: AnalysisResult,
        response_format: str,
    ) -> str:
        """Generate formatted response using LLM."""
        format_instructions = {
            "markdown": "Use formatação Markdown com títulos (##), listas (-) e **negrito** para destaques.",
            "plain": "Use texto simples sem formatação especial.",
            "executive": "Seja extremamente conciso. Máximo 3-4 parágrafos curtos.",
        }

        prompt = f"""Pergunta do usuário: {query}

## Análise Disponível

**Resumo:** {analysis.summary}

**Principais Descobertas:**
{chr(10).join(f'- {f}' for f in analysis.key_findings) if analysis.key_findings else 'N/A'}

**Métricas Financeiras:**
{self._format_metrics(analysis.financial_metrics)}

**Riscos Identificados:**
{chr(10).join(f'- {r}' for r in analysis.risks) if analysis.risks else 'N/A'}

**Oportunidades:**
{chr(10).join(f'- {o}' for o in analysis.opportunities) if analysis.opportunities else 'N/A'}

**Sentimento Geral:** {analysis.sentiment}

**Fontes:** {', '.join(analysis.sources_used) if analysis.sources_used else 'Dados de mercado'}

## Instruções de Formatação
{format_instructions.get(response_format, format_instructions['markdown'])}

Gere uma resposta completa e bem estruturada que responda diretamente à pergunta do usuário.
Inclua os dados mais relevantes da análise de forma natural no texto."""

        response = await self.invoke_llm(user_message=prompt)

        if response_format == "markdown":
            response = self._add_footer(response, analysis.sources_used)

        return response

    def _format_metrics(self, metrics: dict) -> str:
        """Format financial metrics for display."""
        if not metrics:
            return "N/A"

        lines = []
        for key, value in metrics.items():
            if isinstance(value, float):
                formatted_value = f"{value:,.2f}"
            elif isinstance(value, int):
                formatted_value = f"{value:,}"
            else:
                formatted_value = str(value)
            lines.append(f"- {key}: {formatted_value}")

        return "\n".join(lines)

    def _add_footer(self, content: str, sources: list[str]) -> str:
        """Add footer with sources and disclaimers."""
        footer_parts = ["\n\n---\n"]

        if sources:
            footer_parts.append("**Fontes utilizadas:**")
            for source in sources[:5]:
                footer_parts.append(f"- {source}")

        footer_parts.append("\n**Aviso Legal:**")
        footer_parts.append(self.DISCLAIMERS[0])

        return content + "\n".join(footer_parts)

    def _generate_fallback_response(
        self,
        query: str,
        state: AgentState,
    ) -> str:
        """Generate fallback response when analysis is not available."""
        collected_data = state.get("collected_data")

        parts = ["Não foi possível realizar uma análise completa para sua consulta.\n"]

        if collected_data and collected_data.market_data:
            parts.append("## Dados de Mercado Disponíveis\n")
            for md in collected_data.market_data:
                parts.append(f"""
**{md.ticker} - {md.company_name}**
- Preço: R$ {md.current_price:.2f}
- Variação: {md.change_percent:+.2f}%
""")

        if collected_data and collected_data.news_items:
            parts.append("\n## Notícias Recentes\n")
            for news in collected_data.news_items[:3]:
                parts.append(f"- {news.title} ({news.source})\n")

        parts.append("\n---\n")
        parts.append("*Para uma análise mais detalhada, tente reformular sua pergunta.*")

        return "".join(parts)
