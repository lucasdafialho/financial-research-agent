from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.logging import get_logger
from src.infrastructure.cache import CacheService

logger = get_logger("rate_limit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""

    def __init__(
        self,
        app: any,
        cache_service: CacheService,
        requests_per_minute: int = 60,
        exclude_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._cache = cache_service
        self._limit = requests_per_minute
        self._window = 60
        self._exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        if request.url.path in self._exclude_paths:
            return await call_next(request)

        identifier = self._get_identifier(request)

        allowed, remaining = await self._cache.check_rate_limit(
            identifier=identifier,
            limit=self._limit,
            window=self._window,
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit of {self._limit} requests per minute exceeded",
                    "retry_after": self._window,
                },
                headers={
                    "Retry-After": str(self._window),
                    "X-RateLimit-Limit": str(self._limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(self._limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _get_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"apikey:{api_key}"

        return f"ip:{client_ip}"
