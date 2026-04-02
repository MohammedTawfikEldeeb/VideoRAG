from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_async_session


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_async_session():
        yield session
