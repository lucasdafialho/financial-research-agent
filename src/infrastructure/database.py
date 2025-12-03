from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.config.logging import LoggerMixin
from src.config.settings import Settings


class Base(DeclarativeBase):
    """Base class for all database models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


class Document(Base):
    """Document metadata model."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company: Mapped[str] = mapped_column(String(255), index=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    document_type: Mapped[str] = mapped_column(String(50), index=True)
    reference_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="pt-BR")
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class QueryHistory(Base):
    """Query history model for analytics."""

    __tablename__ = "query_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    query_text: Mapped[str] = mapped_column(Text)
    intent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tickers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int] = mapped_column(default=0)
    processing_time_ms: Mapped[float] = mapped_column(default=0.0)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DatabaseService(LoggerMixin):
    """Database service for managing PostgreSQL connections and operations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=settings.debug,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def initialize(self) -> None:
        """Initialize database tables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.info("database_initialized")

    async def close(self) -> None:
        """Close database connections."""
        await self._engine.dispose()
        self.logger.info("database_closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.session() as session:
                await session.execute(func.now())
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
        await _database_service.initialize()
    return _database_service
