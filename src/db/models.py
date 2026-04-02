from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative SQLAlchemy base."""


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("idx_conv_thread_video_created", "thread_id", "video_name", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(255), index=True)
    video_name: Mapped[str] = mapped_column(String(500), index=True)
    role: Mapped[MessageRole] = mapped_column(SqlEnum(MessageRole, name="message_role"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
