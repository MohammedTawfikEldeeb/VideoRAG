# Quickstart: VideoRAG LangGraph Agent

**Branch**: `001-langgraph-agent-design` | **Date**: 2026-04-01

---

## What Is Being Built

A conversational agent that wraps the existing VideoRAG MCP tools in a LangGraph graph. Users can ask questions about videos across multiple sessions; the agent remembers context, compresses long conversations, and can return image frames alongside text.

---

## New Dependencies

Add to `pyproject.toml`:

```toml
"langgraph-checkpoint-sqlite>=2.0",
```

No other new packages are required. `langgraph`, `langchain-core`, and `opik` are already present.

---

## New Files

| File | Role |
|------|------|
| `src/agent/state.py` | **Modify**: add `image_base64: Optional[str]` field |
| `src/agent/tools.py` | **New**: LangChain `@tool` wrappers delegating to service layer |
| `src/agent/nodes.py` | **New**: `router_node`, `tool_node`, `general_node`, `summarize_node` |
| `src/agent/graph.py` | **New**: Graph definition, conditional edges, `SqliteSaver` checkpointer |
| `src/config.py` | **Modify**: add `MEMORY_DB_PATH`, `AGENT_MODEL`, `ROUTER_MODEL` |
| `data/` | **New dir**: created at runtime; holds `memory.db` |

---

## Environment Variables (`.env`)

```env
# Existing — no changes needed
OPENROUTER_API_KEY=...
GROQ_API_KEY=...

# New (optional — defaults shown)
MEMORY_DB_PATH=./data/memory.db
AGENT_MODEL=openai/gpt-4o-mini
ROUTER_MODEL=openai/gpt-4o-mini
```

---

## Basic Usage

```python
from langchain_core.messages import HumanMessage
from src.agent.graph import build_graph

# Build and compile graph (done once at startup)
graph = build_graph()

# Start a new session
config = {"configurable": {"thread_id": "user-session-001"}}
result = graph.invoke(
    {"messages": [HumanMessage(content="What is this video about?")]},
    config
)
print(result["messages"][-1].content)

# Resume same session later
result = graph.invoke(
    {"messages": [HumanMessage(content="And what happens in the last scene?")]},
    config   # same thread_id restores prior context
)
```

---

## Graph Execution Flow

```
User message arrives
        │
   [router_node]  ← decides tool vs. general
        │
   ┌────┴─────┐
[tool_node] [general_node]
        │
 [should_summarise?]
        │
  > 10 msgs → [summarize_node] → END
  ≤ 10 msgs → END
```

---

## Summarization Behavior

After more than 10 messages accumulate:
1. The agent summarizes the full history into `state["summary"]`
2. All messages except the last 2 are deleted from `state["messages"]`
3. On the next turn, the summary is prepended as a system message so the LLM retains context

Each summarization *extends* the previous summary — no context is discarded.

---

## Docker Notes

The `data/` directory holding `memory.db` must be volume-mounted to survive container restarts:

```yaml
# docker-compose.yml addition
volumes:
  - ./data:/app/data
```

Set `MEMORY_DB_PATH=/app/data/memory.db` in the container environment.
