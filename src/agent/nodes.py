"""LangGraph nodes for the VideoRAG agent."""

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image

from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode as LangGraphToolNode
from loguru import logger
from moviepy import VideoFileClip

from src.agent.prompts import ROUTING_SYSTEM_PROMPT, TOOL_USE_SYSTEM_PROMPT, GENERAL_SYSTEM_PROMPT
from src.agent.state import AgentState, RouterOutput
from src.agent.tools import (
    get_video_clip_from_user_query,
    get_video_clip_from_image,
    ask_question_about_video,
)
from src.config import get_settings

logger = logger.bind(name="AgentNodes")
settings = get_settings()


def router_node(state: AgentState) -> dict[str, Any]:

    logger.info("Router node executing")

    llm = ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.ROUTER_MODEL,
    )

    # Build message list with routing prompt and optional summary
    messages = [SystemMessage(content=ROUTING_SYSTEM_PROMPT.format())]

    # Inject summary if present
    summary = state.get("summary", "")
    if summary:
        messages.append(SystemMessage(content=f"Summary of prior conversation:\n{summary}"))

    messages.extend(state["messages"])

    # Use structured output to get boolean routing decision
    structured_llm = llm.with_structured_output(RouterOutput)

    try:
        response: RouterOutput = structured_llm.invoke(messages)
        route_decision = response.requires_tools
    except Exception as e:
        logger.error(f"Router LLM call failed: {e}")
        # Default to general response on error
        route_decision = False

    logger.info(f"Router decision: {'tool' if route_decision else 'general'}")
    return {"route_type": route_decision}


def general_node(state: AgentState) -> dict[str, Any]:

    logger.info("General node executing")

    llm = ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.AGENT_MODEL,
    )

    # Build message list with general prompt and optional summary
    messages = [SystemMessage(content=GENERAL_SYSTEM_PROMPT.format())]

    # Inject summary if present
    summary = state.get("summary", "")
    if summary:
        messages.append(SystemMessage(content=f"Summary of prior conversation:\n{summary}"))

    messages.extend(state["messages"])

    response = llm.invoke(messages)
    logger.info("General response generated")

    return {
        "messages": [response],
        "turn_count": 1,
    }


def tool_node(state: AgentState) -> dict[str, Any]:

    logger.info("Tool node executing")

    # Prepare tools
    tools = [
        get_video_clip_from_user_query,
        get_video_clip_from_image,
        ask_question_about_video,
    ]

    llm = ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.AGENT_MODEL,
    )

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Check if image is provided
    is_image_provided = state.get("image_base64") is not None

    # Build message list with tool prompt and optional summary
    messages = [SystemMessage(content=TOOL_USE_SYSTEM_PROMPT.format(is_image_provided=is_image_provided))]

    # Inject summary if present
    summary = state.get("summary", "")
    if summary:
        messages.append(SystemMessage(content=f"Summary of prior conversation:\n{summary}"))

    messages.extend(state["messages"])

    # Get LLM response with tool calls
    response = llm_with_tools.invoke(messages)

    # Execute tools if any were called
    tool_results = []
    image_base64 = None

    if hasattr(response, "tool_calls") and response.tool_calls:
        logger.info(f"Executing {len(response.tool_calls)} tool call(s)")

        # Use LangGraph's ToolNode to execute tool calls
        tool_executor = LangGraphToolNode(tools)

        # Execute tools - ToolNode expects state dict with messages
        tool_state = {"messages": [response]}
        tool_output = tool_executor.invoke(tool_state)

        # Extract tool results
        for tool_msg in tool_output.get("messages", []):
            if hasattr(tool_msg, "content"):
                tool_results.append({
                    "tool_name": getattr(tool_msg, "name", "unknown"),
                    "result": tool_msg.content,
                })

                # Check if result is a video clip path - extract first frame
                result_str = str(tool_msg.content)
                if result_str.endswith(".mp4") and Path(result_str).exists():
                    try:
                        logger.info(f"Extracting first frame from {result_str}")
                        with VideoFileClip(result_str) as clip:
                            # Get first frame at t=0
                            frame = clip.get_frame(0)
                            pil_image = Image.fromarray(frame)
                            buffer = io.BytesIO()
                            pil_image.save(buffer, format="PNG")
                            image_bytes = buffer.getvalue()
                            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                            logger.info("First frame extracted successfully")
                    except Exception as e:
                        logger.error(f"Failed to extract frame: {e}")

        # Add tool messages to response
        messages_to_return = [response] + tool_output.get("messages", [])
    else:
        logger.info("No tool calls in response")
        messages_to_return = [response]

    return {
        "messages": messages_to_return,
        "tool_results": tool_results,
        "image_base64": image_base64,
        "turn_count": 1,
    }


def summarize_node(state: AgentState) -> dict[str, Any]:

    logger.info("Summarize node executing")

    llm = ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.AGENT_MODEL,
    )

    # Build summarization prompt
    existing_summary = state.get("summary", "")
    if existing_summary:
        summary_prompt = f"This is the current summary: {existing_summary}\n\nExtend it with the new messages above."
    else:
        summary_prompt = "Summarise the conversation above in a few sentences."

    # Add prompt as final message
    messages_to_summarize = list(state["messages"]) + [HumanMessage(content=summary_prompt)]

    # Generate summary
    response = llm.invoke(messages_to_summarize)
    new_summary = response.content

    # Delete all but last 2 messages
    messages_to_delete = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]

    logger.info(f"Summary generated, removing {len(messages_to_delete)} old messages")

    return {
        "summary": new_summary,
        "messages": messages_to_delete,
    }


