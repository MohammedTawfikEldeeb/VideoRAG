"""Chat request and response schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    thread_id: str = Field(..., min_length=1)
    video_name: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    thread_id: str
    video_name: str
    role: Literal["assistant"] = "assistant"
    message: str
