from fastapi import APIRouter, Depends
from kombu import Connection
from redis import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.config import get_settings

router = APIRouter(tags=["base"])
settings = get_settings()


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_db_session)) -> dict[str, object]:
    dependencies = {
        "broker": "ok",
        "result_backend": "ok",
        "database": "ok",
    }

    try:
        with Connection(settings.CELERY_BROKER_URL, connect_timeout=3) as connection:
            connection.ensure_connection(max_retries=1)
    except Exception:
        dependencies["broker"] = "unreachable"

    try:
        redis_client = Redis.from_url(settings.CELERY_RESULT_BACKEND)
        redis_client.ping()
    except Exception:
        dependencies["result_backend"] = "unreachable"

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        dependencies["database"] = "unreachable"

    status = "healthy" if all(value == "ok" for value in dependencies.values()) else "degraded"
    return {
        "status": status,
        "version": settings.APP_VERSION,
        "dependencies": dependencies,
    }
