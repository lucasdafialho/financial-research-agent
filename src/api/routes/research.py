from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_workflow
from src.api.schemas.requests import QueryRequest
from src.api.schemas.responses import AnalysisResultResponse, QueryResponse
from src.workflows.graph import FinancialResearchWorkflow

router = APIRouter(prefix="/research", tags=["Research"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Submit Research Query",
    description="Submit a financial research query for analysis",
)
async def submit_query(
    request: QueryRequest,
    workflow: FinancialResearchWorkflow = Depends(get_workflow),
) -> QueryResponse:
    """Process a financial research query."""
    try:
        response = await workflow.run(
            query=request.query,
            user_id=request.user_id,
        )

        analysis_response = None
        if response.analysis:
            analysis_response = AnalysisResultResponse(
                summary=response.analysis.summary,
                key_findings=response.analysis.key_findings,
                financial_metrics=response.analysis.financial_metrics,
                risks=response.analysis.risks,
                opportunities=response.analysis.opportunities,
                sentiment=response.analysis.sentiment,
                confidence_score=response.analysis.confidence_score,
            )

        return QueryResponse(
            response_id=response.response_id,
            query_id=response.query_id,
            content=response.content,
            format=response.format,
            analysis=analysis_response,
            sources=response.sources,
            disclaimers=response.disclaimers,
            processing_time_ms=response.processing_time_ms,
            timestamp=response.timestamp,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}",
        )


@router.post(
    "/query/stream",
    summary="Submit Research Query (Streaming)",
    description="Submit a query and receive streaming response",
)
async def submit_query_stream(
    request: QueryRequest,
    workflow: FinancialResearchWorkflow = Depends(get_workflow),
):
    """Process query with streaming response."""
    from fastapi.responses import StreamingResponse

    async def generate():
        try:
            response, state = await workflow.run_with_state(
                query=request.query,
                user_id=request.user_id,
            )

            import json

            yield f"data: {json.dumps({'type': 'start', 'query_id': response.query_id})}\n\n"

            completed_agents = state.get("completed_agents", [])
            for agent in completed_agents:
                yield f"data: {json.dumps({'type': 'agent_complete', 'agent': agent})}\n\n"

            yield f"data: {json.dumps({'type': 'content', 'content': response.content})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'processing_time_ms': response.processing_time_ms})}\n\n"

        except Exception as e:
            import json

            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.get(
    "/workflow",
    summary="Get Workflow Structure",
    description="Get the structure of the research workflow",
)
async def get_workflow_structure(
    workflow: FinancialResearchWorkflow = Depends(get_workflow),
) -> dict:
    """Get workflow graph visualization data."""
    return workflow.get_graph_visualization()
