"""Conversation history schemas."""

from datetime import datetime

from pydantic import BaseModel

from src.schemas.pagination import PaginatedResponse


class MessageResponse(BaseModel):
    id: int
    thread_id: str
    video_name: str
    role: str
    message: str
    created_at: datetime


HistoryResponse = PaginatedResponse[MessageResponse]
