from typing import Literal

from src.agents.analyst import AnalystAgent
from src.agents.collector import CollectorAgent
from src.agents.rag import RAGAgent
from src.agents.reporter import ReporterAgent
from src.agents.router import RouterAgent
from src.config.logging import LoggerMixin
from src.config.settings import Settings
from src.core.types import AgentState
from src.infrastructure.cache import CacheService
from src.rag.retriever import RAGRetriever


class WorkflowNodes(LoggerMixin):
    """Container for all workflow nodes and routing logic."""

    def __init__(
        self,
        settings: Settings,
        cache_service: CacheService | None = None,
        rag_retriever: RAGRetriever | None = None,
    ) -> None:
        self._settings = settings
        self._cache = cache_service
        self._retriever = rag_retriever

        self._router = RouterAgent(settings)
        self._collector = CollectorAgent(settings, cache_service)
        self._rag = RAGAgent(settings, rag_retriever) if rag_retriever else None
        self._analyst = AnalystAgent(settings, rag_retriever)
        self._reporter = ReporterAgent(settings)

    async def route_query(self, state: AgentState) -> AgentState:
        """Route the query and determine which agents to invoke."""
        self.logger.info("workflow_node", node="router", action="start")
        result = await self._router.execute(state)
        self.logger.info("workflow_node", node="router", action="complete")
        return result

    async def collect_data(self, state: AgentState) -> AgentState:
        """Collect data from external sources."""
        self.logger.info("workflow_node", node="collector", action="start")
        result = await self._collector.execute(state)
        self.logger.info("workflow_node", node="collector", action="complete")
        return result

    async def retrieve_documents(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents using RAG."""
        self.logger.info("workflow_node", node="rag", action="start")
        if self._rag:
            result = await self._rag.execute(state)
        else:
            self.logger.warning("rag_agent_not_configured")
            result = state
        self.logger.info("workflow_node", node="rag", action="complete")
        return result

    async def analyze_data(self, state: AgentState) -> AgentState:
        """Analyze collected data and documents."""
        self.logger.info("workflow_node", node="analyst", action="start")
        result = await self._analyst.execute(state)
        self.logger.info("workflow_node", node="analyst", action="complete")
        return result

    async def generate_report(self, state: AgentState) -> AgentState:
        """Generate final report."""
        self.logger.info("workflow_node", node="reporter", action="start")
        result = await self._reporter.execute(state)
        self.logger.info("workflow_node", node="reporter", action="complete")
        return result

    def should_collect_data(
        self,
        state: AgentState,
    ) -> Literal["collect", "skip_collect"]:
        """Determine if data collection is needed."""
        intent = state.get("intent")
        if not intent:
            return "collect"

        if intent.requires_market_data or intent.tickers:
            return "collect"

        return "skip_collect"

    def should_retrieve_documents(
        self,
        state: AgentState,
    ) -> Literal["retrieve", "skip_retrieve"]:
        """Determine if RAG retrieval is needed."""
        intent = state.get("intent")
        if not intent:
            return "retrieve"

        if intent.requires_rag:
            return "retrieve"

        return "skip_retrieve"

    def should_continue_analysis(
        self,
        state: AgentState,
    ) -> Literal["analyze", "need_more_data", "error"]:
        """Determine if analysis can proceed."""
        errors = state.get("errors", [])
        if len(errors) > 3:
            return "error"

        collected_data = state.get("collected_data")
        rag_context = state.get("rag_context")

        has_data = collected_data and (
            collected_data.market_data
            or collected_data.news_items
            or collected_data.raw_data
        )
        has_documents = rag_context and rag_context.chunks

        if has_data or has_documents:
            return "analyze"

        intent = state.get("intent")
        if intent and not intent.requires_market_data and not intent.requires_rag:
            return "analyze"

        return "need_more_data"

    def is_complete(
        self,
        state: AgentState,
    ) -> Literal["complete", "retry", "error"]:
        """Check if workflow is complete."""
        response = state.get("response")
        errors = state.get("errors", [])

        if response and response.content:
            return "complete"

        if len(errors) > 5:
            return "error"

        return "retry"
