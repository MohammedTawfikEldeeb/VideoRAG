import asyncio
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.routers.base import router as base_router
from src.api.routers.chat import router as chat_router
from src.api.routers.history import router as history_router
from src.api.routers.process import router as process_router
from src.config import get_settings


def _run_database_migrations() -> None:
    settings = get_settings()
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("script_location", "src/db/migrations")
    alembic_config.set_main_option("sqlalchemy.url", settings.CONVERSATIONS_DB_URL)
    command.upgrade(alembic_config, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(_run_database_migrations)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="VideoRAG API", version=get_settings().APP_VERSION, lifespan=lifespan)

    app.include_router(base_router)
    app.include_router(process_router, prefix="/process")
    app.include_router(chat_router)
    app.include_router(history_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception while processing {} {}", request.method, request.url.path)
        logger.debug("Exception details: {}", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
