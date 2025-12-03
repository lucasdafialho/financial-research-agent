from typing import Any
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from src.config.logging import LoggerMixin
from src.config.settings import Settings
from src.core.types import DocumentChunk


class VectorStoreService(LoggerMixin):
    """Qdrant vector store service for semantic search."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncQdrantClient | None = None
        self._collection_name = settings.qdrant_collection_name
        self._vector_size = settings.qdrant_vector_size

    async def connect(self) -> None:
        """Connect to Qdrant."""
        self._client = AsyncQdrantClient(
            host=self._settings.qdrant_host,
            port=self._settings.qdrant_port,
        )
        await self._ensure_collection()
        self.logger.info("vector_store_connected")

    async def close(self) -> None:
        """Close Qdrant connection."""
        if self._client:
            await self._client.close()
            self.logger.info("vector_store_closed")

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise RuntimeError("Vector store not connected. Call connect() first.")
        return self._client

    async def _ensure_collection(self) -> None:
        """Ensure the collection exists with proper configuration."""
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if self._collection_name not in collection_names:
            await self.client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                ),
            )
            self.logger.info("collection_created", collection=self._collection_name)

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Insert or update document chunks with their embeddings."""
        if not chunks:
            return 0

        points = [
            PointStruct(
                id=chunk.chunk_id or str(uuid4()),
                vector=chunk.embedding or [],
                payload={
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata,
                },
            )
            for chunk in chunks
            if chunk.embedding
        ]

        if not points:
            return 0

        await self.client.upsert(
            collection_name=self._collection_name,
            points=points,
        )
        self.logger.info("chunks_upserted", count=len(points))
        return len(points)

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float = 0.0,
    ) -> list[tuple[DocumentChunk, float]]:
        """Search for similar chunks."""
        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results: list[ScoredPoint] = await self.client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
        )

        chunks_with_scores: list[tuple[DocumentChunk, float]] = []
        for result in results:
            payload = result.payload or {}
            chunk = DocumentChunk(
                chunk_id=str(result.id),
                document_id=payload.get("document_id", ""),
                content=payload.get("content", ""),
                page_number=payload.get("page_number"),
                chunk_index=payload.get("chunk_index", 0),
                metadata={
                    k: v
                    for k, v in payload.items()
                    if k not in ("document_id", "content", "page_number", "chunk_index")
                },
            )
            chunks_with_scores.append((chunk, result.score))

        return chunks_with_scores

    async def delete_by_document_id(self, document_id: str) -> bool:
        """Delete all chunks for a document."""
        try:
            await self.client.delete(
                collection_name=self._collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )
            self.logger.info("chunks_deleted", document_id=document_id)
            return True
        except Exception as e:
            self.logger.error("delete_chunks_error", document_id=document_id, error=str(e))
            return False

    async def get_collection_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        info = await self.client.get_collection(self._collection_name)
        return {
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.value,
        }

    async def health_check(self) -> bool:
        """Check Qdrant connectivity."""
        try:
            await self.client.get_collections()
            return True
        except Exception as e:
            self.logger.error("vector_store_health_check_failed", error=str(e))
            return False


_vector_store_service: VectorStoreService | None = None


async def get_vector_store_service(settings: Settings | None = None) -> VectorStoreService:
    """Get or create the vector store service singleton."""
    global _vector_store_service
    if _vector_store_service is None:
        if settings is None:
            from src.config.settings import get_settings

            settings = get_settings()
        _vector_store_service = VectorStoreService(settings)
        await _vector_store_service.connect()
    return _vector_store_service
