from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import close_services, init_services
from src.api.middleware.error_handler import error_handler_middleware
from src.api.middleware.logging import LoggingMiddleware
from src.api.routes import (
    documents_router,
    health_router,
    market_router,
    research_router,
)
from src.config.logging import setup_logging
from src.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()
    setup_logging(settings)

    await init_services(settings)

    yield

    await close_services()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Financial Research Agent API",
        description="""
        AI-powered financial research agent with multi-agent orchestration.

        ## Features

        - **Research Queries**: Ask natural language questions about Brazilian stocks
        - **Market Data**: Real-time quotes, historical data, and company info
        - **Document Processing**: Upload and index financial documents
        - **RAG-based Analysis**: Intelligent document retrieval and analysis

        ## Agents

        - **Router**: Analyzes queries and determines processing path
        - **Collector**: Gathers data from external sources (Yahoo Finance, CVM, News)
        - **RAG**: Retrieves relevant documents from the knowledge base
        - **Analyst**: Analyzes data and generates insights
        - **Reporter**: Synthesizes findings into coherent responses
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(LoggingMiddleware)

    @app.middleware("http")
    async def error_handling(request, call_next):
        return await error_handler_middleware(request, call_next)

    app.include_router(health_router)
    app.include_router(research_router)
    app.include_router(documents_router)
    app.include_router(market_router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": "Financial Research Agent API",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app


app = create_app()
