from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="financial-research-agent")
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    debug: bool = Field(default=False)
    secret_key: SecretStr = Field(...)

    database_url: str = Field(...)
    database_pool_size: int = Field(default=10)

    mongodb_url: str = Field(default="mongodb://localhost:27017")
    mongodb_database: str = Field(default="financial_research")

    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_cache_ttl: int = Field(default=3600)

    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_collection_name: str = Field(default="financial_documents")
    qdrant_vector_size: int = Field(default=1536)

    openai_api_key: SecretStr | None = Field(default=None)
    anthropic_api_key: SecretStr | None = Field(default=None)
    cohere_api_key: SecretStr | None = Field(default=None)

    llm_provider: Literal["openai", "anthropic"] = Field(default="openai")
    llm_model: str = Field(default="gpt-4-turbo-preview")
    llm_temperature: float = Field(default=0.1)
    llm_max_tokens: int = Field(default=4096)

    embedding_provider: Literal["openai", "cohere"] = Field(default="openai")
    embedding_model: str = Field(default="text-embedding-3-small")

    news_api_key: SecretStr | None = Field(default=None)

    rag_chunk_size: int = Field(default=512)
    rag_chunk_overlap: int = Field(default=50)
    rag_top_k: int = Field(default=10)
    rag_rerank_top_k: int = Field(default=5)

    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=60)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="json")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "sqlite")):
            raise ValueError("Database URL must be PostgreSQL or SQLite")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
