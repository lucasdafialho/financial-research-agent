from typing import Any


class BaseApplicationError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(BaseApplicationError):
    """Raised when input validation fails."""

    pass


class ExternalAPIError(BaseApplicationError):
    """Raised when an external API call fails."""

    def __init__(
        self,
        message: str,
        service: str,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.service = service
        self.status_code = status_code
        self.details["service"] = service
        if status_code:
            self.details["status_code"] = status_code


class DataCollectionError(BaseApplicationError):
    """Raised when data collection fails."""

    def __init__(
        self,
        message: str,
        source: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.source = source
        self.details["source"] = source


class DocumentProcessingError(BaseApplicationError):
    """Raised when document processing fails."""

    def __init__(
        self,
        message: str,
        document_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.document_id = document_id
        if document_id:
            self.details["document_id"] = document_id


class RAGError(BaseApplicationError):
    """Raised when RAG operations fail."""

    pass


class AgentError(BaseApplicationError):
    """Raised when an agent encounters an error."""

    def __init__(
        self,
        message: str,
        agent_name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.agent_name = agent_name
        self.details["agent_name"] = agent_name


class DatabaseError(BaseApplicationError):
    """Raised when database operations fail."""

    pass


class CacheError(BaseApplicationError):
    """Raised when cache operations fail."""

    pass


class RateLimitError(BaseApplicationError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.details["retry_after"] = retry_after
