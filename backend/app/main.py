"""FastAPI application entrypoint."""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import close_db, init_db
from app.exceptions import setup_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.routers import conversations, documents, health
from app.services.conversation_service import ConversationService
from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.llm import LLMService
from app.services.reranker import RerankerService
from app.services.retrieval import RetrievalService
from app.services.storage import StorageService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()

    # Initialize and store singleton services in app.state for dependency injection.
    app.state.storage_service = StorageService(settings)
    app.state.embedding_service = EmbeddingService(settings)
    app.state.reranker_service = RerankerService(settings)
    app.state.llm_service = LLMService(settings)
    app.state.conversation_service = ConversationService(settings)
    app.state.retrieval_service = RetrievalService(
        settings,
        embedding_service=app.state.embedding_service,
        reranker_service=app.state.reranker_service,
    )
    app.state.ingestion_service = IngestionService(
        settings,
        storage_service=app.state.storage_service,
        embedding_service=app.state.embedding_service,
    )

    await init_db()
    await app.state.storage_service.ensure_bucket()

    logger.info("Application startup complete")
    yield
    logger.info("Application shutting down")
    await close_db()


def create_application() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="RAG Document Q&A",
        description="Production-ready RAG backend for document Q&A.",
        version="0.2.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def add_request_id_and_logging(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        logger.info(
            "Request started: %s %s (request_id=%s)",
            request.method,
            request.url.path,
            request_id,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled exception in request (request_id=%s)", request_id)
            response = JSONResponse(
                status_code=500,
                content={"error": "InternalServerError", "detail": "An unexpected error occurred"},
            )

        duration = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "Request completed: %s %s status=%s duration=%.2fms (request_id=%s)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
            request_id,
        )
        return response

    setup_exception_handlers(application)

    application.include_router(health.router, prefix="/api")
    application.include_router(documents.router, prefix="/api")
    application.include_router(conversations.router, prefix="/api")

    return application


app = create_application()
