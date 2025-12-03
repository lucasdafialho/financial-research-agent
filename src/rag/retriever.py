from typing import Any

import cohere

from src.config.logging import LoggerMixin
from src.config.settings import Settings
from src.core.types import DocumentChunk, RAGContext
from src.infrastructure.vector_store import VectorStoreService
from src.rag.embeddings import EmbeddingService


class RAGRetriever(LoggerMixin):
    """Service for retrieving relevant document chunks using RAG."""

    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreService,
    ) -> None:
        self._settings = settings
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._top_k = settings.rag_top_k
        self._rerank_top_k = settings.rag_rerank_top_k

        self._cohere_client = None
        if settings.cohere_api_key:
            self._cohere_client = cohere.Client(settings.cohere_api_key.get_secret_value())

    async def retrieve(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
        rerank: bool = True,
    ) -> RAGContext:
        """Retrieve relevant chunks for a query."""
        top_k = top_k or self._top_k

        query_embedding = await self._embedding_service.embed_query(query)

        results = await self._vector_store.search(
            query_vector=query_embedding,
            top_k=top_k * 2 if rerank else top_k,
            filters=filters,
        )

        if not results:
            return RAGContext(
                chunks=[],
                total_chunks_found=0,
                query_embedding=query_embedding,
                search_metadata={"filters": filters, "reranked": False},
            )

        chunks = [chunk for chunk, _ in results]
        scores = [score for _, score in results]

        if rerank and self._cohere_client and len(chunks) > 1:
            chunks, scores = await self._rerank_chunks(query, chunks, scores)
            chunks = chunks[: self._rerank_top_k]

        self.logger.info(
            "chunks_retrieved",
            query_length=len(query),
            chunks_found=len(chunks),
            top_score=scores[0] if scores else 0,
            reranked=rerank and self._cohere_client is not None,
        )

        return RAGContext(
            chunks=chunks,
            total_chunks_found=len(results),
            query_embedding=query_embedding,
            search_metadata={
                "filters": filters,
                "reranked": rerank and self._cohere_client is not None,
                "scores": scores[:10],
            },
        )

    async def _rerank_chunks(
        self,
        query: str,
        chunks: list[DocumentChunk],
        initial_scores: list[float],
    ) -> tuple[list[DocumentChunk], list[float]]:
        """Rerank chunks using Cohere reranker."""
        if not self._cohere_client:
            return chunks, initial_scores

        try:
            documents = [chunk.content for chunk in chunks]

            response = self._cohere_client.rerank(
                query=query,
                documents=documents,
                model="rerank-multilingual-v3.0",
                top_n=len(documents),
            )

            reranked_chunks: list[DocumentChunk] = []
            reranked_scores: list[float] = []

            for result in response.results:
                reranked_chunks.append(chunks[result.index])
                reranked_scores.append(result.relevance_score)

            return reranked_chunks, reranked_scores

        except Exception as e:
            self.logger.warning("rerank_failed", error=str(e))
            return chunks, initial_scores

    async def retrieve_by_ticker(
        self,
        query: str,
        ticker: str,
        document_types: list[str] | None = None,
        top_k: int | None = None,
    ) -> RAGContext:
        """Retrieve chunks filtered by ticker and optionally document type."""
        filters: dict[str, Any] = {"ticker": ticker.upper()}

        if document_types:
            pass

        return await self.retrieve(query, filters=filters, top_k=top_k)

    async def retrieve_by_company(
        self,
        query: str,
        company: str,
        top_k: int | None = None,
    ) -> RAGContext:
        """Retrieve chunks filtered by company name."""
        filters: dict[str, Any] = {"company": company}
        return await self.retrieve(query, filters=filters, top_k=top_k)

    async def hybrid_search(
        self,
        query: str,
        keywords: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> RAGContext:
        """Perform hybrid search combining semantic and keyword matching."""
        semantic_results = await self.retrieve(
            query=query,
            filters=filters,
            top_k=top_k or self._top_k,
            rerank=False,
        )

        if keywords:
            keyword_boost = self._calculate_keyword_boost(
                semantic_results.chunks,
                keywords,
            )

            boosted_chunks: list[tuple[DocumentChunk, float]] = []
            for chunk in semantic_results.chunks:
                boost = keyword_boost.get(chunk.chunk_id, 0)
                score = semantic_results.search_metadata.get("scores", [0])[
                    semantic_results.chunks.index(chunk)
                ]
                boosted_chunks.append((chunk, score + boost * 0.2))

            boosted_chunks.sort(key=lambda x: x[1], reverse=True)

            return RAGContext(
                chunks=[c for c, _ in boosted_chunks],
                total_chunks_found=semantic_results.total_chunks_found,
                query_embedding=semantic_results.query_embedding,
                search_metadata={
                    **semantic_results.search_metadata,
                    "keyword_boosted": True,
                    "keywords": keywords,
                },
            )

        return semantic_results

    def _calculate_keyword_boost(
        self,
        chunks: list[DocumentChunk],
        keywords: list[str],
    ) -> dict[str, float]:
        """Calculate keyword boost scores for chunks."""
        boost_scores: dict[str, float] = {}

        for chunk in chunks:
            content_lower = chunk.content.lower()
            matches = sum(1 for kw in keywords if kw.lower() in content_lower)
            if matches > 0:
                boost_scores[chunk.chunk_id] = matches / len(keywords)

        return boost_scores

    def format_context(
        self,
        rag_context: RAGContext,
        max_tokens: int = 4000,
    ) -> str:
        """Format retrieved chunks into context string for LLM."""
        if not rag_context.chunks:
            return ""

        context_parts: list[str] = []
        current_length = 0
        char_per_token = 4

        for i, chunk in enumerate(rag_context.chunks):
            chunk_text = f"[Fonte {i + 1}]\n{chunk.content}\n"

            if chunk.metadata:
                meta_parts = []
                if "company" in chunk.metadata:
                    meta_parts.append(f"Empresa: {chunk.metadata['company']}")
                if "document_type" in chunk.metadata:
                    meta_parts.append(f"Tipo: {chunk.metadata['document_type']}")
                if "reference_date" in chunk.metadata:
                    meta_parts.append(f"Data: {chunk.metadata['reference_date']}")
                if meta_parts:
                    chunk_text = f"[Fonte {i + 1} - {', '.join(meta_parts)}]\n{chunk.content}\n"

            chunk_tokens = len(chunk_text) // char_per_token

            if current_length + chunk_tokens > max_tokens:
                break

            context_parts.append(chunk_text)
            current_length += chunk_tokens

        return "\n---\n".join(context_parts)
