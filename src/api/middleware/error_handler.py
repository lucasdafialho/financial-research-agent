from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from src.config.logging import get_logger
from src.core.exceptions import (
    AgentError,
    BaseApplicationError,
    ExternalAPIError,
    RateLimitError,
    ValidationError,
)

logger = get_logger("error_handler")


async def error_handler_middleware(
    request: Request,
    call_next: Callable,
) -> Response:
    """Middleware for handling exceptions and returning proper error responses."""
    try:
        return await call_next(request)

    except ValidationError as e:
        logger.warning(
            "validation_error",
            path=request.url.path,
            error=str(e),
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": "VALIDATION_ERROR",
                "message": e.message,
                "details": e.details,
            },
        )

    except RateLimitError as e:
        logger.warning(
            "rate_limit_exceeded",
            path=request.url.path,
        )
        headers = {}
        if e.retry_after:
            headers["Retry-After"] = str(e.retry_after)

        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": e.message,
                "details": e.details,
            },
            headers=headers,
        )

    except ExternalAPIError as e:
        logger.error(
            "external_api_error",
            service=e.service,
            status_code=e.status_code,
            error=str(e),
        )
        return JSONResponse(
            status_code=502,
            content={
                "error": "EXTERNAL_API_ERROR",
                "message": "Failed to fetch data from external service",
                "details": {"service": e.service},
            },
        )

    except AgentError as e:
        logger.error(
            "agent_error",
            agent=e.agent_name,
            error=str(e),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "AGENT_ERROR",
                "message": "An error occurred during processing",
                "details": {"agent": e.agent_name},
            },
        )

    except BaseApplicationError as e:
        logger.error(
            "application_error",
            code=e.code,
            error=str(e),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": e.code,
                "message": e.message,
                "details": e.details,
            },
        )

    except Exception as e:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            error=str(e),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            },
        )
