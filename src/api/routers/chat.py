from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent import build_graph
from src.api.dependencies import get_db_session
from src.db.models import ConversationMessage, MessageRole
from src.schemas.chat import ChatRequest, ChatResponse
from src.services.video.registry import get_registry

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, session: AsyncSession = Depends(get_db_session)) -> ChatResponse:
    if payload.video_name not in get_registry():
        raise HTTPException(
            status_code=400,
            detail=f"Video '{payload.video_name}' has not been processed yet or does not exist.",
        )

    graph = build_graph()
    graph_output = await graph.ainvoke(
        {
            "messages": [
                SystemMessage(
                    content=(
                        f"Current video context: {payload.video_name}. "
                        "Use this value as the video_path argument for any video tool call."
                    )
                ),
                HumanMessage(content=payload.message),
            ]
        },
        config={"configurable": {"thread_id": f"{payload.thread_id}:{payload.video_name}"}},
    )

    assistant_message = next(
        (
            message
            for message in reversed(graph_output.get("messages", []))
            if isinstance(message, AIMessage)
        ),
        None,
    )
    if assistant_message is None:
        raise HTTPException(status_code=500, detail="Agent did not return a response.")

    session.add_all(
        [
            ConversationMessage(
                thread_id=payload.thread_id,
                video_name=payload.video_name,
                role=MessageRole.USER,
                message=payload.message,
            ),
            ConversationMessage(
                thread_id=payload.thread_id,
                video_name=payload.video_name,
                role=MessageRole.ASSISTANT,
                message=str(assistant_message.content),
            ),
        ]
    )
    await session.commit()

    return ChatResponse(
        thread_id=payload.thread_id,
        video_name=payload.video_name,
        role="assistant",
        message=str(assistant_message.content),
    )
