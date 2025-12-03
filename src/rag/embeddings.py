from typing import Literal

import cohere
from openai import AsyncOpenAI

from src.config.logging import LoggerMixin
from src.config.settings import Settings


class EmbeddingService(LoggerMixin):
    """Service for generating text embeddings using OpenAI or Cohere."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = settings.embedding_provider
        self._model = settings.embedding_model

        if self._provider == "openai":
            api_key = settings.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API key required for OpenAI embeddings")
            self._openai_client = AsyncOpenAI(api_key=api_key.get_secret_value())
            self._cohere_client = None
        else:
            api_key = settings.cohere_api_key
            if not api_key:
                raise ValueError("Cohere API key required for Cohere embeddings")
            self._cohere_client = cohere.Client(api_key.get_secret_value())
            self._openai_client = None

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        texts = [self._clean_text(t) for t in texts]

        if self._provider == "openai":
            return await self._embed_openai(texts)
        else:
            return await self._embed_cohere(texts)

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI."""
        if not self._openai_client:
            raise RuntimeError("OpenAI client not initialized")

        batch_size = 100
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            response = await self._openai_client.embeddings.create(
                model=self._model,
                input=batch,
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            self.logger.debug(
                "embeddings_generated",
                provider="openai",
                batch_size=len(batch),
                total_tokens=response.usage.total_tokens,
            )

        return all_embeddings

    async def _embed_cohere(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Cohere."""
        if not self._cohere_client:
            raise RuntimeError("Cohere client not initialized")

        batch_size = 96
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            response = self._cohere_client.embed(
                texts=batch,
                model=self._model,
                input_type="search_document",
            )

            all_embeddings.extend(response.embeddings)

            self.logger.debug(
                "embeddings_generated",
                provider="cohere",
                batch_size=len(batch),
            )

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query."""
        query = self._clean_text(query)

        if self._provider == "openai":
            return await self._embed_openai_query(query)
        else:
            return await self._embed_cohere_query(query)

    async def _embed_openai_query(self, query: str) -> list[float]:
        """Generate query embedding using OpenAI."""
        if not self._openai_client:
            raise RuntimeError("OpenAI client not initialized")

        response = await self._openai_client.embeddings.create(
            model=self._model,
            input=query,
        )

        return response.data[0].embedding

    async def _embed_cohere_query(self, query: str) -> list[float]:
        """Generate query embedding using Cohere."""
        if not self._cohere_client:
            raise RuntimeError("Cohere client not initialized")

        response = self._cohere_client.embed(
            texts=[query],
            model=self._model,
            input_type="search_query",
        )

        return response.embeddings[0]

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean text before embedding."""
        text = " ".join(text.split())
        text = text.strip()
        if len(text) > 8191:
            text = text[:8191]
        return text

    @property
    def vector_size(self) -> int:
        """Return the embedding vector size."""
        return self._settings.qdrant_vector_size
