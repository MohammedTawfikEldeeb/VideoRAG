
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.db.models import ConversationMessage
from src.schemas.history import HistoryResponse, MessageResponse
from src.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryResponse)
async def get_history(
    thread_id: str = Query(..., min_length=1),
    video_name: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> HistoryResponse:
    count_stmt = select(func.count()).select_from(ConversationMessage).where(
        ConversationMessage.thread_id == thread_id,
        ConversationMessage.video_name == video_name,
    )
    total = (await session.execute(count_stmt)).scalar_one()

    items_stmt = (
        select(ConversationMessage)
        .where(
            ConversationMessage.thread_id == thread_id,
            ConversationMessage.video_name == video_name,
        )
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(items_stmt)).scalars().all()
    items = [
        MessageResponse(
            id=row.id,
            thread_id=row.thread_id,
            video_name=row.video_name,
            role=row.role.value,
            message=row.message,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return PaginatedResponse[MessageResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
    )
