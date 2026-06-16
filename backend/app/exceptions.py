"""Domain exceptions and global error handlers for the FastAPI application."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.logging_config import get_logger
from app.models.schemas import ErrorResponse

logger = get_logger(__name__)


class RAGException(Exception):
    """Base exception for application-specific errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(RAGException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}", status_code=404
        )


class ValidationError(RAGException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)


class LLMServiceError(RAGException):
    def __init__(self, message: str = "LLM service unavailable"):
        super().__init__(message=message, status_code=503)


class StorageError(RAGException):
    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message=message, status_code=500)


def setup_exception_handlers(app) -> None:
    """Register global exception handlers on the FastAPI application."""

    @app.exception_handler(RAGException)
    async def handle_rag_exception(request: Request, exc: RAGException):
        logger.warning(
            "Application error: %s (status=%d) path=%s",
            exc.message,
            exc.status_code,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=exc.__class__.__name__, detail=exc.message).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_generic_exception(request: Request, exc: Exception):
        logger.exception("Unhandled error at %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="InternalServerError",
                detail="An unexpected error occurred",
            ).model_dump(),
        )
