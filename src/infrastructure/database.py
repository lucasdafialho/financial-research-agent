import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from collections.abc import AsyncGenerator

import asyncpg

from src.config.logging import LoggerMixin
from src.config.settings import Settings


class DatabaseService(LoggerMixin):
    """PostgreSQL database service using asyncpg directly."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None
        self._dsn = self._parse_dsn(settings.database_url)

    def _parse_dsn(self, url: str) -> str:
        """Convert SQLAlchemy-style URL to asyncpg DSN."""
        return url.replace("postgresql+asyncpg://", "postgresql://")

    async def connect(self) -> None:
        """Create connection pool."""
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=5,
            max_size=self._settings.database_pool_size,
        )
        await self._create_tables()
        self.logger.info("database_connected")

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self.logger.info("database_closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id VARCHAR(36) PRIMARY KEY,
                    company VARCHAR(255) NOT NULL,
                    ticker VARCHAR(20) NOT NULL,
                    document_type VARCHAR(50) NOT NULL,
                    reference_date TIMESTAMP NOT NULL,
                    source_url TEXT,
                    file_hash VARCHAR(64) UNIQUE,
                    page_count INTEGER,
                    language VARCHAR(10) DEFAULT 'pt-BR',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_documents_ticker ON documents(ticker);
                CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company);
                CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
                CREATE INDEX IF NOT EXISTS idx_documents_reference_date ON documents(reference_date);
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id VARCHAR(36) PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    intent_type VARCHAR(50),
                    tickers JSONB,
                    response_summary TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    processing_time_ms FLOAT DEFAULT 0,
                    user_id VARCHAR(36),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_query_history_user ON query_history(user_id);
                CREATE INDEX IF NOT EXISTS idx_query_history_created ON query_history(created_at);
            """)

        self.logger.info("database_tables_created")

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database connection from the pool."""
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a connection with transaction."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def insert_document(
        self,
        document_id: str,
        company: str,
        ticker: str,
        document_type: str,
        reference_date: datetime,
        source_url: str | None = None,
        file_hash: str | None = None,
        page_count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Insert a new document record."""
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO documents (
                    id, company, ticker, document_type, reference_date,
                    source_url, file_hash, page_count, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (file_hash) DO NOTHING
                """,
                document_id,
                company,
                ticker.upper(),
                document_type,
                reference_date,
                source_url,
                file_hash,
                page_count,
                json.dumps(metadata or {}),
            )
        return document_id

    async def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Get a document by ID."""
        async with self.connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE id = $1",
                document_id,
            )
            return dict(row) if row else None

    async def get_documents_by_ticker(
        self,
        ticker: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get documents by ticker."""
        async with self.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM documents
                WHERE ticker = $1
                ORDER BY reference_date DESC
                LIMIT $2
                """,
                ticker.upper(),
                limit,
            )
            return [dict(row) for row in rows]

    async def get_documents_by_company(
        self,
        company: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get documents by company name."""
        async with self.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM documents
                WHERE company ILIKE $1
                ORDER BY reference_date DESC
                LIMIT $2
                """,
                f"%{company}%",
                limit,
            )
            return [dict(row) for row in rows]

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document by ID."""
        async with self.connection() as conn:
            result = await conn.execute(
                "DELETE FROM documents WHERE id = $1",
                document_id,
            )
            return result == "DELETE 1"

    async def insert_query_history(
        self,
        query_id: str,
        query_text: str,
        intent_type: str | None = None,
        tickers: list[str] | None = None,
        response_summary: str | None = None,
        tokens_used: int = 0,
        processing_time_ms: float = 0,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Insert a query history record."""
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO query_history (
                    id, query_text, intent_type, tickers, response_summary,
                    tokens_used, processing_time_ms, user_id, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                query_id,
                query_text,
                intent_type,
                json.dumps(tickers or []),
                response_summary,
                tokens_used,
                processing_time_ms,
                user_id,
                json.dumps(metadata or {}),
            )
        return query_id

    async def get_recent_queries(
        self,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent queries."""
        async with self.connection() as conn:
            if user_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM query_history
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    user_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM query_history
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            return [dict(row) for row in rows]

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.connection() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            self.logger.error("database_health_check_failed", error=str(e))
            return False


_database_service: DatabaseService | None = None


async def get_database_service(settings: Settings | None = None) -> DatabaseService:
    """Get or create the database service singleton."""
    global _database_service
    if _database_service is None:
        if settings is None:
            from src.config.settings import get_settings
            settings = get_settings()
        _database_service = DatabaseService(settings)
        await _database_service.connect()
    return _database_service
