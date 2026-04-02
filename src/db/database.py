from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

settings = get_settings()


def _ensure_sqlite_directory_exists() -> None:
    database_url = make_url(settings.CONVERSATIONS_DB_URL)
    if database_url.drivername.startswith("sqlite") and database_url.database:
        Path(database_url.database).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory_exists()

engine = create_async_engine(settings.CONVERSATIONS_DB_URL, future=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
