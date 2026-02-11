"""FastAPI application for ontology API.

This module sets up the FastAPI application with routers, error handlers,
and middleware.
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ontologizer.api.routers import (
    taxonomy_router,
    topic_router,
)

from ontologizer.api.errors import http_exception_handler, value_error_handler
from ontologizer.relational.database import dispose_engine_async, get_engine
from ontologizer.relational.database import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for FastAPI.

    Handles startup and shutdown events using Advanced-Alchemy.

    Args:
        app: FastAPI application

    Yields:
        None
    """
    # Startup: Initialize database engine
    from ontologizer.settings import get_settings

    settings = get_settings()
    logger.info(
        "Starting Ontology API",
        extra={"environment": settings.environment},
    )

    # Get engine (initializes Advanced-Alchemy config and listeners)
    engine = get_engine()

    # Create database tables (for development - use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database engine initialized via Advanced-Alchemy")

    yield

    # Shutdown: Clean up resources
    await dispose_engine_async()
    logger.info("Ontology API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Ontology API",
        description="REST API for topic taxonomy and knowledge management",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore
    app.add_exception_handler(ValueError, value_error_handler)  # type: ignore

    app.include_router(taxonomy_router)
    app.include_router(topic_router)

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        """Root endpoint.

        Returns:
            API information
        """
        return {
            "name": "Ontology API",
            "version": "0.1.0",
            "docs": "/docs",
        }

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            Health status
        """
        return {"status": "healthy"}

    return app


# Create application instance
app = create_app()
