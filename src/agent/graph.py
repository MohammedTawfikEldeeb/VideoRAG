"""LangGraph graph construction for VideoRAG agent."""

from pathlib import Path
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, END, START
from loguru import logger

from src.agent.state import AgentState
from src.agent.nodes import router_node, tool_node, general_node, summarize_node
from src.config import get_settings

logger = logger.bind(name="AgentGraph")
settings = get_settings()


def route_decision(state: AgentState) -> Literal["tool_node", "general_node"]:
 
    route_type = state.get("route_type", False)
    return "tool_node" if route_type else "general_node"


def should_summarise(state: AgentState) -> Literal["summarise", "continue"]:

    message_count = len(state.get("messages", []))
    return "summarise" if message_count > 10 else "continue"


def build_graph():
 
    logger.info("Building VideoRAG agent graph with summarization and SQLite persistence")

    # Ensure data directory exists
    db_path = Path(settings.MEMORY_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"SQLite checkpoint database: {db_path}")

    # Initialize SQLite checkpointer
    checkpointer = SqliteSaver.from_conn_string(str(db_path))

    # Create state graph
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("router_node", router_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("general_node", general_node)
    builder.add_node("summarize_node", summarize_node)

    # Set entry point
    builder.add_edge(START, "router_node")

    # Add conditional routing from router
    builder.add_conditional_edges(
        "router_node",
        route_decision,
        {
            "tool_node": "tool_node",
            "general_node": "general_node",
        },
    )

    # Add conditional edges for summarization from both paths
    builder.add_conditional_edges(
        "tool_node",
        should_summarise,
        {
            "summarise": "summarize_node",
            "continue": END,
        },
    )

    builder.add_conditional_edges(
        "general_node",
        should_summarise,
        {
            "summarise": "summarize_node",
            "continue": END,
        },
    )

    # Summarize node leads to END
    builder.add_edge("summarize_node", END)

    # Compile with checkpointer for persistence
    graph = builder.compile(checkpointer=checkpointer)

    logger.info("Graph compiled successfully with SQLite checkpointer and summarization")
    return graph


