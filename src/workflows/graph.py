import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from langgraph.graph import END, StateGraph

from src.config.logging import LoggerMixin
from src.config.settings import Settings
from src.core.types import AgentState, ResearchQuery, ResearchResponse
from src.infrastructure.cache import CacheService
from src.rag.retriever import RAGRetriever
from src.workflows.nodes import WorkflowNodes


class FinancialResearchWorkflow(LoggerMixin):
    """Main workflow orchestrator using LangGraph."""

    def __init__(
        self,
        settings: Settings,
        cache_service: CacheService | None = None,
        rag_retriever: RAGRetriever | None = None,
    ) -> None:
        self._settings = settings
        self._nodes = WorkflowNodes(settings, cache_service, rag_retriever)
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        workflow.add_node("router", self._nodes.route_query)
        workflow.add_node("collector", self._nodes.collect_data)
        workflow.add_node("rag", self._nodes.retrieve_documents)
        workflow.add_node("analyst", self._nodes.analyze_data)
        workflow.add_node("reporter", self._nodes.generate_report)

        workflow.set_entry_point("router")

        workflow.add_conditional_edges(
            "router",
            self._route_after_router,
            {
                "collect_and_retrieve": "collector",
                "collect_only": "collector",
                "retrieve_only": "rag",
                "analyze_direct": "analyst",
            },
        )

        workflow.add_conditional_edges(
            "collector",
            self._route_after_collector,
            {
                "retrieve": "rag",
                "analyze": "analyst",
            },
        )

        workflow.add_edge("rag", "analyst")
        workflow.add_edge("analyst", "reporter")

        workflow.add_conditional_edges(
            "reporter",
            self._route_after_reporter,
            {
                "complete": END,
                "retry": "analyst",
                "error": END,
            },
        )

        return workflow.compile()

    def _route_after_router(self, state: AgentState) -> str:
        """Determine routing after router node."""
        intent = state.get("intent")
        if not intent:
            return "collect_and_retrieve"

        needs_collection = intent.requires_market_data or intent.tickers
        needs_rag = intent.requires_rag

        if needs_collection and needs_rag:
            return "collect_and_retrieve"
        elif needs_collection:
            return "collect_only"
        elif needs_rag:
            return "retrieve_only"
        else:
            return "analyze_direct"

    def _route_after_collector(self, state: AgentState) -> str:
        """Determine routing after collector node."""
        intent = state.get("intent")
        if intent and intent.requires_rag:
            return "retrieve"
        return "analyze"

    def _route_after_reporter(self, state: AgentState) -> str:
        """Determine routing after reporter node."""
        return self._nodes.is_complete(state)

    async def run(
        self,
        query: str,
        user_id: str | None = None,
    ) -> ResearchResponse:
        """Execute the workflow for a given query."""
        start_time = time.perf_counter()
        query_id = str(uuid4())

        self.logger.info(
            "workflow_started",
            query_id=query_id,
            query_length=len(query),
        )

        research_query = ResearchQuery(
            query_id=query_id,
            raw_query=query,
            user_id=user_id,
            timestamp=datetime.utcnow(),
        )

        initial_state: AgentState = {
            "query": research_query,
            "errors": [],
            "metadata": {
                "start_time": datetime.utcnow().isoformat(),
                "user_id": user_id,
            },
            "completed_agents": [],
        }

        try:
            final_state = await self._graph.ainvoke(initial_state)

            processing_time = (time.perf_counter() - start_time) * 1000

            response = final_state.get("response")
            if response:
                response.processing_time_ms = processing_time
                self.logger.info(
                    "workflow_completed",
                    query_id=query_id,
                    processing_time_ms=processing_time,
                    agents_used=final_state.get("completed_agents", []),
                )
                return response

            self.logger.warning(
                "workflow_no_response",
                query_id=query_id,
                errors=final_state.get("errors", []),
            )

            return ResearchResponse(
                response_id=str(uuid4()),
                query_id=query_id,
                content="Não foi possível processar sua consulta. Por favor, tente novamente.",
                format="plain",
                processing_time_ms=processing_time,
            )

        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            self.logger.exception(
                "workflow_error",
                query_id=query_id,
                error=str(e),
                processing_time_ms=processing_time,
            )

            return ResearchResponse(
                response_id=str(uuid4()),
                query_id=query_id,
                content=f"Erro ao processar consulta: {str(e)}",
                format="plain",
                processing_time_ms=processing_time,
            )

    async def run_with_state(
        self,
        query: str,
        user_id: str | None = None,
    ) -> tuple[ResearchResponse, AgentState]:
        """Execute workflow and return both response and final state."""
        start_time = time.perf_counter()
        query_id = str(uuid4())

        research_query = ResearchQuery(
            query_id=query_id,
            raw_query=query,
            user_id=user_id,
        )

        initial_state: AgentState = {
            "query": research_query,
            "errors": [],
            "metadata": {},
            "completed_agents": [],
        }

        final_state = await self._graph.ainvoke(initial_state)
        processing_time = (time.perf_counter() - start_time) * 1000

        response = final_state.get("response")
        if response:
            response.processing_time_ms = processing_time
            return response, final_state

        fallback_response = ResearchResponse(
            response_id=str(uuid4()),
            query_id=query_id,
            content="Processamento incompleto",
            processing_time_ms=processing_time,
        )

        return fallback_response, final_state

    def get_graph_visualization(self) -> dict[str, Any]:
        """Get graph structure for visualization."""
        return {
            "nodes": [
                {"id": "router", "label": "Router Agent"},
                {"id": "collector", "label": "Collector Agent"},
                {"id": "rag", "label": "RAG Agent"},
                {"id": "analyst", "label": "Analyst Agent"},
                {"id": "reporter", "label": "Reporter Agent"},
            ],
            "edges": [
                {"from": "router", "to": "collector", "label": "needs data"},
                {"from": "router", "to": "rag", "label": "needs docs"},
                {"from": "router", "to": "analyst", "label": "direct"},
                {"from": "collector", "to": "rag", "label": "needs docs"},
                {"from": "collector", "to": "analyst", "label": "analyze"},
                {"from": "rag", "to": "analyst", "label": "always"},
                {"from": "analyst", "to": "reporter", "label": "always"},
                {"from": "reporter", "to": "END", "label": "complete"},
            ],
        }
