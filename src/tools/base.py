import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.logging import LoggerMixin
from src.core.exceptions import ExternalAPIError

T = TypeVar("T")


class ToolResult(BaseModel, Generic[T]):
    """Result wrapper for tool execution."""

    success: bool
    data: T | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    source: str = ""


class BaseTool(ABC, LoggerMixin):
    """Abstract base class for all external tools."""

    name: str = "base_tool"
    description: str = "Base tool"
    max_retries: int = 3
    timeout_seconds: int = 30

    def __init__(self) -> None:
        self._retry_decorator = retry(
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
        )

    @abstractmethod
    async def _execute(self, **kwargs: Any) -> Any:
        """Execute the tool operation. Must be implemented by subclasses."""
        pass

    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        """Execute the tool with retry logic and timing."""
        start_time = time.perf_counter()

        try:
            wrapped_execute = self._retry_decorator(self._execute)
            result = await wrapped_execute(**kwargs)
            execution_time = (time.perf_counter() - start_time) * 1000

            self.log_operation(
                f"{self.name}_execute",
                status="success",
                duration_ms=execution_time,
            )

            return ToolResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
                source=self.name,
            )

        except RetryError as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            error_msg = f"Max retries exceeded: {str(e.last_attempt.exception())}"

            self.log_operation(
                f"{self.name}_execute",
                status="failed",
                duration_ms=execution_time,
                error=error_msg,
            )

            return ToolResult(
                success=False,
                error=error_msg,
                execution_time_ms=execution_time,
                source=self.name,
            )

        except ExternalAPIError as e:
            execution_time = (time.perf_counter() - start_time) * 1000

            self.log_operation(
                f"{self.name}_execute",
                status="failed",
                duration_ms=execution_time,
                error=str(e),
            )

            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                source=self.name,
            )

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000

            self.logger.exception(
                f"{self.name}_unexpected_error",
                error=str(e),
            )

            return ToolResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                execution_time_ms=execution_time,
                source=self.name,
            )
