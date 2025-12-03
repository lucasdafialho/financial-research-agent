from typing import Any

from src.config.settings import Settings, get_settings
from src.infrastructure.cache import CacheService
from src.infrastructure.database import DatabaseService
from src.infrastructure.vector_store import VectorStoreService
from src.rag.chunker import DocumentChunker
from src.rag.embeddings import EmbeddingService
from src.rag.processor import DocumentProcessor
from src.rag.retriever import RAGRetriever
from src.workflows.graph import FinancialResearchWorkflow

_services: dict[str, Any] = {}


async def init_services(settings: Settings) -> None:
    """Initialize all services."""
    global _services

    try:
        db = DatabaseService(settings)
        await db.connect()
        _services["database"] = db
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        _services["database"] = None

    try:
        cache = CacheService(settings)
        await cache.connect()
        _services["cache"] = cache
    except Exception as e:
        print(f"Warning: Cache initialization failed: {e}")
        _services["cache"] = None

    try:
        vector_store = VectorStoreService(settings)
        await vector_store.connect()
        _services["vector_store"] = vector_store
    except Exception as e:
        print(f"Warning: Vector store initialization failed: {e}")
        _services["vector_store"] = None

    try:
        embedding_service = EmbeddingService(settings)
        _services["embedding_service"] = embedding_service
    except Exception as e:
        print(f"Warning: Embedding service initialization failed: {e}")
        _services["embedding_service"] = None

    if _services.get("embedding_service") and _services.get("vector_store"):
        retriever = RAGRetriever(
            settings,
            _services["embedding_service"],
            _services["vector_store"],
        )
        _services["retriever"] = retriever

        chunker = DocumentChunker(settings)
        processor = DocumentProcessor(
            settings,
            _services["embedding_service"],
            _services["vector_store"],
            chunker,
        )
        _services["processor"] = processor

    workflow = FinancialResearchWorkflow(
        settings,
        _services.get("cache"),
        _services.get("retriever"),
    )
    _services["workflow"] = workflow


async def close_services() -> None:
    """Close all services."""
    global _services

    if _services.get("database"):
        await _services["database"].close()

    if _services.get("cache"):
        await _services["cache"].close()

    if _services.get("vector_store"):
        await _services["vector_store"].close()

    _services.clear()


async def get_services() -> dict[str, Any]:
    """Get all services."""
    return _services


async def get_database() -> DatabaseService | None:
    """Get database service."""
    return _services.get("database")


async def get_cache() -> CacheService | None:
    """Get cache service."""
    return _services.get("cache")


async def get_vector_store() -> VectorStoreService | None:
    """Get vector store service."""
    return _services.get("vector_store")


async def get_workflow() -> FinancialResearchWorkflow:
    """Get workflow instance."""
    workflow = _services.get("workflow")
    if not workflow:
        settings = get_settings()
        workflow = FinancialResearchWorkflow(settings)
        _services["workflow"] = workflow
    return workflow


async def get_document_processor() -> DocumentProcessor:
    """Get document processor."""
    processor = _services.get("processor")
    if not processor:
        raise RuntimeError("Document processor not initialized")
    return processor


async def get_retriever() -> RAGRetriever:
    """Get RAG retriever."""
    retriever = _services.get("retriever")
    if not retriever:
        raise RuntimeError("RAG retriever not initialized")
    return retriever
