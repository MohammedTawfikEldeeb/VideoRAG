# Agent Interface Contract

**Branch**: `001-langgraph-agent-design` | **Date**: 2026-04-01

This document defines the external interface of the VideoRAG LangGraph agent — specifically how callers invoke the agent and what they receive in return.

---

## Invocation Contract

The agent is invoked as a compiled LangGraph graph. Callers interact via `.invoke()` (sync) or `.ainvoke()` (async).

### Input

```python
# Minimum required input
input_state = {
    "messages": [HumanMessage(content="<user message>")]
}

# Optional: include image input
input_state = {
    "messages": [HumanMessage(content="Find the scene matching this image")],
    "image_base64": "<base64-encoded image string>"
}

# Required invocation config
config = {
    "configurable": {
        "thread_id": "<unique session identifier>"  # string, caller-provided
    }
}
```

| Input Field | Required | Type | Description |
|-------------|----------|------|-------------|
| `messages` | Yes | `list[HumanMessage]` | Must contain at least one message for the current turn |
| `image_base64` | No | `str \| None` | Base64 image for visual search; triggers `get_video_clip_from_image` tool |
| `thread_id` (config) | Yes | `str` | Session identifier for SQLite checkpointing |

### Output

The graph returns the final `AgentState` after all nodes have executed.

```python
result = graph.invoke(input_state, config)

# Access the agent's reply
reply_text = result["messages"][-1].content   # AIMessage content

# Access image output (if any)
image_data = result.get("image_base64")       # str | None

# Check turn count
turns = result["turn_count"]
```

| Output Field | Type | Description |
|-------------|------|-------------|
| `messages[-1]` | `AIMessage` | The agent's reply for this turn |
| `image_base64` | `str \| None` | Base64 image response (first frame of extracted clip), or `None` |
| `tool_results` | `list[dict]` | Raw tool outputs accumulated this session |
| `summary` | `str` | Current rolling summary (may be empty string) |
| `turn_count` | `int` | Total turns taken in this session |

---

## Thread ID Convention

- Thread IDs are opaque strings; the agent imposes no format.
- Recommended: use a stable user/session identifier (e.g., UUID, username, or chat session ID).
- The same `thread_id` passed in subsequent invocations restores the full prior conversation.
- A new `thread_id` starts a fresh conversation with no prior history.

---

## Error Conditions

| Condition | Behavior |
|-----------|----------|
| Tool call fails (e.g., video not indexed) | Agent catches error, returns a text explanation in `messages[-1]`; `image_base64` remains `None` |
| SQLite DB unavailable | Raises `sqlite3.OperationalError` at graph compile time or first invocation |
| Empty `messages` input | Raises `ValueError` from LangGraph state validation |
| `image_base64` provided but no matching frame found | Returns closest match or text fallback; no error raised |

---

## Streaming Contract (optional, future)

The agent supports streaming via `.stream()`. Each yielded chunk is a partial state update dict with the node name as key.

```python
for chunk in graph.stream(input_state, config, stream_mode="updates"):
    node_name, state_update = list(chunk.items())[0]
    # e.g., ("router_node", {"route_type": True})
    # e.g., ("tool_node", {"messages": [...], "image_base64": "..."})
```

---

## Video Path Convention

All tool calls require a `video_path` argument identifying the target video. This path must:
1. Match a video previously indexed via the `process_video` tool.
2. Be relative to the working directory or an absolute path accessible to the process.

The agent does not manage video paths — the caller (or user message) must provide them.
