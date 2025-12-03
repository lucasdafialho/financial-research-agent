from src.agents.base import BaseAgent
from src.config.settings import Settings
from src.core.types import AgentState, QueryIntentType, RAGContext
from src.rag.retriever import RAGRetriever


class RAGAgent(BaseAgent):
    """Agent responsible for retrieving relevant documents using RAG."""

    name = "rag"
    description = "Retrieves and processes relevant documents from the knowledge base"

    def __init__(
        self,
        settings: Settings,
        retriever: RAGRetriever,
    ) -> None:
        super().__init__(settings)
        self._retriever = retriever

    @property
    def system_prompt(self) -> str:
        return """Você é um agente de recuperação de informações especializado em documentos financeiros.
Sua função é buscar e selecionar os documentos mais relevantes para responder à consulta do usuário.
Você prioriza documentos oficiais como balanços, relatórios trimestrais e fatos relevantes."""

    async def execute(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents for the query."""
        query = state.get("query")
        intent = state.get("intent")

        if not query or not intent:
            return self.add_error(state, ValueError("Query and intent required"))

        if not intent.requires_rag:
            self.logger.info("rag_skipped", reason="not_required_by_intent")
            return self.update_state(
                state,
                {"rag_context": RAGContext(chunks=[], total_chunks_found=0)},
            )

        try:
            search_query = self._build_search_query(query.raw_query, intent)
            filters = self._build_filters(intent)
            keywords = self._extract_keywords(query.raw_query, intent)

            if keywords:
                rag_context = await self._retriever.hybrid_search(
                    query=search_query,
                    keywords=keywords,
                    filters=filters,
                    top_k=self._settings.rag_top_k,
                )
            else:
                rag_context = await self._retriever.retrieve(
                    query=search_query,
                    filters=filters,
                    top_k=self._settings.rag_top_k,
                )

            self.logger.info(
                "rag_retrieval_complete",
                chunks_found=len(rag_context.chunks),
                total_chunks=rag_context.total_chunks_found,
                filters=filters,
            )

            return self.update_state(state, {"rag_context": rag_context})

        except Exception as e:
            self.logger.exception("rag_error", error=str(e))
            return self.add_error(state, e)

    def _build_search_query(self, raw_query: str, intent: any) -> str:
        """Build optimized search query based on intent."""
        if intent.intent_type == QueryIntentType.FINANCIAL_ANALYSIS:
            return f"{raw_query} resultados financeiros balanço demonstrações"
        elif intent.intent_type == QueryIntentType.DOCUMENT_SEARCH:
            return raw_query
        elif intent.intent_type == QueryIntentType.COMPARISON:
            return f"{raw_query} indicadores métricas comparativo"
        else:
            return raw_query

    def _build_filters(self, intent: any) -> dict | None:
        """Build search filters based on intent."""
        filters = {}

        if intent.tickers and len(intent.tickers) == 1:
            filters["ticker"] = intent.tickers[0]

        if intent.entities.get("companies") and len(intent.entities["companies"]) == 1:
            filters["company"] = intent.entities["companies"][0]

        return filters if filters else None

    def _extract_keywords(self, query: str, intent: any) -> list[str] | None:
        """Extract important keywords for hybrid search."""
        financial_terms = [
            "receita",
            "lucro",
            "prejuízo",
            "ebitda",
            "margem",
            "dívida",
            "caixa",
            "ativo",
            "passivo",
            "patrimônio",
            "dividendo",
            "ação",
            "resultado",
            "trimestre",
            "semestre",
            "ano",
            "crescimento",
            "queda",
            "variação",
        ]

        query_lower = query.lower()
        found_keywords = [term for term in financial_terms if term in query_lower]

        found_keywords.extend(intent.tickers)

        return found_keywords if found_keywords else None

    async def retrieve_for_ticker(
        self,
        ticker: str,
        query: str,
        document_types: list[str] | None = None,
    ) -> RAGContext:
        """Direct retrieval for a specific ticker."""
        return await self._retriever.retrieve_by_ticker(
            query=query,
            ticker=ticker,
            document_types=document_types,
        )

    def format_context_for_analysis(
        self,
        rag_context: RAGContext,
        max_tokens: int = 4000,
    ) -> str:
        """Format retrieved context for the analyst agent."""
        return self._retriever.format_context(rag_context, max_tokens)
