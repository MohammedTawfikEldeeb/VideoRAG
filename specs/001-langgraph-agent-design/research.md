# Research: VideoRAG LangGraph Agent

**Branch**: `001-langgraph-agent-design` | **Date**: 2026-04-01

---

## 1. Tool Integration: LangGraph ↔ MCP Tools

### Decision
The agent will call the video service layer **directly** (importing from `src/services/`) using LangChain `@tool`-decorated wrappers, rather than connecting to the FastMCP server via an MCP client.

### Rationale
- The video service functions (`VideoSearchEngine`, `VideoProcessor`, `extract_video_clip`) are plain Python — they can be imported directly.
- Calling through an MCP client (`langchain-mcp-adapters`) would require spawning or connecting to the MCP server as a subprocess, adding latency and a startup dependency.
- The MCP server layer exists for external clients (Claude Desktop, Inspector). The agent is an internal consumer; it does not need the network hop.
- Direct calls keep error handling simple and stack traces readable.

### Alternatives Considered
- `langchain-mcp-adapters` / `MultiServerMCPClient`: Valid for cross-process MCP tool invocation. Rejected here because the agent and tools live in the same Python process.
- Calling the FastMCP server via SSE: Possible but over-engineered for in-process usage.

### Implementation
Define a `src/agent/tools.py` module with LangChain `@tool`-decorated functions that delegate to the existing service layer. This keeps MCP server and agent tool definitions independent — both call the same services but are not coupled to each other.

---

## 2. SQLite Checkpointing

### Decision
Use `SqliteSaver` from the `langgraph-checkpoint-sqlite` package (separate install from `langgraph`).

### Rationale
- Zero external infrastructure; single file; works on both local dev and Docker with a volume mount.
- Already decided as the project memory architecture (see session S44).
- `AsyncSqliteSaver` is available for async graphs; `SqliteSaver` covers the sync case.

### Package & Import
```
pip install langgraph-checkpoint-sqlite
# or in pyproject.toml:
# "langgraph-checkpoint-sqlite>=2.0"
```
```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("./data/memory.db")
graph = builder.compile(checkpointer=checkpointer)

# Invocation with thread config:
config = {"configurable": {"thread_id": "session-abc123"}}
result = graph.invoke({"messages": [HumanMessage(content="...")]}, config)
```

### Database Schema (auto-created by SqliteSaver)
Table: `checkpoints`

| Column | Type | Notes |
|--------|------|-------|
| thread_id | TEXT | Session identifier provided by caller |
| checkpoint_ns | TEXT | Namespace (default: "") |
| checkpoint_id | TEXT | UUID of this checkpoint |
| parent_checkpoint_id | TEXT | Previous checkpoint UUID |
| type | TEXT | Serialization type |
| checkpoint | BLOB | Serialized state (messages, summary, etc.) |
| metadata | BLOB | Run metadata |

Thread history is queried via `graph.get_state_history(config)`.

### Alternatives Considered
- `MemorySaver` (in-memory): No persistence across restarts. Good only for testing.
- `AsyncSqliteSaver` (`from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver`): Better for async graphs. Use if the agent graph is compiled with async nodes.
- PostgreSQL checkpointer: External infrastructure; overkill for current single-user scope.

---

## 3. Summary Injection Pattern

### Decision
Before any LLM call in `tool_node` or `general_node`, prepend the rolling summary as a `SystemMessage` if it exists.

### Pattern
```python
from langchain_core.messages import SystemMessage

def build_messages_with_summary(state):
    summary = state.get("summary", "")
    messages = state["messages"]
    if summary:
        return [SystemMessage(content=f"Summary of prior conversation:\n{summary}")] + messages
    return messages
```

### Rationale
Prepending as a `SystemMessage` is the idiomatic LangGraph pattern. It keeps the summary out of the `messages` list (avoiding it being treated as a real turn) while making it visible to the LLM as context.

---

## 4. Conditional Edge Routing

### Decision
Two conditional edges:
1. **After `router_node`**: routes on `state["route_type"]` (True → `"tool_node"`, False → `"general_node"`)
2. **After tool/general response nodes**: routes via `should_summarise()` checking `len(state["messages"]) > 10`

### Pattern
```python
from langgraph.graph import StateGraph, END

def route_decision(state):
    return "tool_node" if state["route_type"] else "general_node"

def should_summarise(state):
    return "summarise" if len(state["messages"]) > 10 else "continue"

builder.add_conditional_edges("router_node", route_decision, {
    "tool_node": "tool_node",
    "general_node": "general_node"
})
builder.add_conditional_edges("tool_node", should_summarise, {
    "summarise": "summarise_node",
    "continue": END
})
builder.add_conditional_edges("general_node", should_summarise, {
    "summarise": "summarise_node",
    "continue": END
})
builder.add_edge("summarise_node", END)
```

---

## 5. Opik Tracing with LangGraph

### Decision
Use `OpikTracer` LangChain callback passed to LLM invocations or to graph `.invoke()` via `callbacks`.

### Pattern
```python
from opik.integrations.langchain import OpikTracer

tracer = OpikTracer(project_name="AgenticVideoRAG")
config = {"configurable": {"thread_id": "..."}, "callbacks": [tracer]}
graph.invoke(input, config)
```

### Rationale
Opik's LangChain integration works transparently with LangGraph since LangGraph builds on LangChain's runnable interface. The existing `opik_config.py` already handles Opik initialization at startup.

---

## 6. Image Input/Output Handling

### Decision
- **Input**: `image_base64` in state carries a user-provided image (base64 string) passed to `get_video_clip_from_image` tool.
- **Output**: `image_base64` is also used for the response — after a clip is extracted, the agent reads the first frame of the output clip as base64 and stores it in state for delivery.

### Rationale
The existing MCP tools return clip file paths (strings). To return image data to the user, a post-tool step reads the clip's first frame using moviepy/PIL and encodes it as base64. This keeps the service layer unchanged while enabling image responses.

### Alternatives Considered
- Returning only the clip file path in the response: Works for CLI clients but not for conversational agents where the user expects inline visual feedback.
- Modifying the MCP tools to return base64 directly: Would break the MCP tool contract for existing clients.
