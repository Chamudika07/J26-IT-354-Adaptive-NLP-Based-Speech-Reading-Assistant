"""Create the single shared FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import router
from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import create_db_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app without opening a database connection or changing its schema."""
    settings = settings if settings is not None else Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(settings.database_url)
        application.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="Adaptive Speech & Reading Assistant API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env in {"development", "test"} else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env in {"development", "test"} else None,
    )
    application.state.settings = settings
    register_exception_handlers(application)
    application.include_router(router, prefix="/api/v1")
    return application
