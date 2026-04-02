"""create conversation messages table"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260402_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    message_role = sa.Enum("user", "assistant", name="message_role")
    message_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("video_name", sa.String(length=500), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_conversation_messages_thread_id",
        "conversation_messages",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_messages_video_name",
        "conversation_messages",
        ["video_name"],
        unique=False,
    )
    op.create_index(
        "idx_conv_thread_video_created",
        "conversation_messages",
        ["thread_id", "video_name", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_conv_thread_video_created", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_video_name", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_thread_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    sa.Enum("user", "assistant", name="message_role").drop(op.get_bind(), checkfirst=True)
