# Data Model: VideoRAG LangGraph Agent

**Branch**: `001-langgraph-agent-design` | **Date**: 2026-04-01

---

## AgentState (Extended)

The core state type threaded through every node in the graph. Defined in `src/agent/state.py`.

### Fields

| Field | Type | Reducer | Description |
|-------|------|---------|-------------|
| `messages` | `list[BaseMessage]` | `add_messages` | Append-only message list. Managed by LangGraph's built-in reducer. Older messages are removed by the summarizer node using `RemoveMessage`. |
| `summary` | `str` | last-write | Rolling cumulative summary of compressed conversation history. Empty string when no summarization has occurred. Extended (not replaced) on each summarization cycle. |
| `route_type` | `bool` | last-write | `True` = tool call required, `False` = general response. Set by `router_node` each turn. |
| `tool_results` | `list[dict]` | `operator.add` | Accumulating list of raw tool outputs for the current session. Each entry is a dict with at least `tool_name` and `result` keys. |
| `turn_count` | `int` | `lambda a, b: a + b` | Monotonically incrementing turn counter. Incremented by 1 at the end of every turn. |
| `image_base64` | `Optional[str]` | last-write | **(New)** Base64-encoded image string. Populated when: (a) user sends an image input for `get_video_clip_from_image`, or (b) agent returns a visual result (first frame of extracted clip). `None` for text-only turns. |

### State Transitions

```
Turn start:  image_base64 = None (cleared at start of each turn)
Router runs: route_type = True | False
If tool:     tool_results += [{"tool_name": ..., "result": ...}]
             image_base64 = <base64 frame if clip extracted, else None>
Summarize:   messages = last 2 messages (rest deleted via RemoveMessage)
             summary = extended summary string
Turn end:    turn_count += 1
```

---

## Graph Topology

```
START
  │
  ▼
[router_node]
  │  conditional on route_type
  ├─ True ──→ [tool_node] ──────────────→ [should_summarise?]
  └─ False ─→ [general_node] ────────────→ [should_summarise?]
                                                │
                                      ┌─────────┴────────────┐
                                "summarise"              "continue"
                                      │                       │
                               [summarize_node]             END
                                      │
                                     END
```

---

## Node Contracts

### `router_node`
- **Input**: `state["messages"]` (full history) + `state["summary"]`
- **Output**: `{"route_type": bool}`
- **LLM call**: Uses `ROUTING_SYSTEM_PROMPT` from `src/agent/prompts.py`. Returns structured output (`bool`).
- **Side effects**: None.

### `tool_node`
- **Input**: `state["messages"]`, `state["summary"]`, `state["image_base64"]` (may carry input image)
- **Output**: `{"messages": [AIMessage(...)], "tool_results": [...], "image_base64": str | None, "turn_count": 1}`
- **LLM call**: Uses `TOOL_USE_SYSTEM_PROMPT`. Model has tools bound. Executes one or more tool calls.
- **Tool execution**: Calls `src/agent/tools.py` wrappers → `src/services/` layer.
- **Image extraction**: If tool result is a clip path, reads first frame as base64 and sets `image_base64`.

### `general_node`
- **Input**: `state["messages"]`, `state["summary"]`
- **Output**: `{"messages": [AIMessage(...)], "turn_count": 1}`
- **LLM call**: Uses `GENERAL_SYSTEM_PROMPT`. No tools bound.
- **Side effects**: None.

### `summarize_node`
- **Input**: `state["messages"]`, `state["summary"]`
- **Output**: `{"summary": str, "messages": [RemoveMessage(id=m.id) for m in messages[:-2]]}`
- **LLM call**: Summarization prompt (extend prior summary or create new).
- **Side effects**: Deletes all but last 2 messages from state via `RemoveMessage`.

---

## Conditional Edge Functions

### `route_decision(state) → str`
```
True  → "tool_node"
False → "general_node"
```

### `should_summarise(state) → str`
```
len(state["messages"]) > 10 → "summarise"
otherwise                   → "continue"
```

---

## SQLite Checkpoint Schema

Managed by `SqliteSaver` from `langgraph-checkpoint-sqlite`. Auto-created on first use.

**File**: `./data/memory.db` (configurable via `MEMORY_DB_PATH` in settings)

**Table**: `checkpoints`

| Column | Type | Notes |
|--------|------|-------|
| `thread_id` | TEXT | Session identifier (provided by caller via `config["configurable"]["thread_id"]`) |
| `checkpoint_ns` | TEXT | Namespace, default `""` |
| `checkpoint_id` | TEXT | UUID of this checkpoint (auto-generated) |
| `parent_checkpoint_id` | TEXT | Previous checkpoint UUID |
| `type` | TEXT | Serialization format |
| `checkpoint` | BLOB | Full serialized `AgentState` |
| `metadata` | BLOB | Run metadata (step, source, writes) |

**Table**: `checkpoint_blobs` (individual state field values per checkpoint)

| Column | Type | Notes |
|--------|------|-------|
| `thread_id` | TEXT | |
| `checkpoint_ns` | TEXT | |
| `channel` | TEXT | State field name (e.g., `messages`, `summary`) |
| `version` | TEXT | |
| `type` | TEXT | |
| `blob` | BLOB | Serialized field value |

**Table**: `checkpoint_writes` (pending writes between checkpoints)

| Column | Type | Notes |
|--------|------|-------|
| `thread_id` | TEXT | Links to checkpoints |
| `checkpoint_ns` | TEXT | |
| `checkpoint_id` | TEXT | |
| `task_id` | TEXT | |
| `idx` | INTEGER | |
| `channel` | TEXT | State field name |
| `type` | TEXT | |
| `blob` | BLOB | Serialized field value |

---

## New Configuration Fields

Added to `src/config.py` `Settings` class:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `MEMORY_DB_PATH` | `str` | `"./data/memory.db"` | Path to SQLite checkpoint database |
| `AGENT_MODEL` | `str` | `"openai/gpt-4o-mini"` | LLM model for agent nodes (via OpenRouter) |
| `ROUTER_MODEL` | `str` | `"openai/gpt-4o-mini"` | LLM model for routing node (can be smaller/faster) |

---

## New Agent Tools Module (`src/agent/tools.py`)

LangChain `@tool` wrappers that delegate to the service layer. Separate from MCP tool definitions.

| Tool Name | Delegates To | Returns |
|-----------|-------------|---------|
| `process_video` | `VideoProcessor.add_video()` | `str` (status message) |
| `get_video_clip_from_user_query` | `VideoSearchEngine.search_by_speech/caption()` + `extract_video_clip()` | `str` (clip path) |
| `get_video_clip_from_image` | `VideoSearchEngine.search_by_image()` + `extract_video_clip()` | `str` (clip path) |
| `ask_question_about_video` | `VideoSearchEngine.get_caption_info()` | `str` (captions) |
