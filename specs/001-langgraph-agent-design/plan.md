# Implementation Plan: VideoRAG LangGraph Agent

**Branch**: `001-langgraph-agent-design` | **Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-langgraph-agent-design/spec.md`

## Summary

Build a LangGraph agent on top of the existing VideoRAG MCP server. The agent routes each user message to either a tool-calling path (3 MCP tools: clip-by-query, clip-by-image, video Q&A) or a general response path. Conversation history is compressed after every 8+ turns using a rolling summarizer node. State is persisted across sessions via SQLite checkpointing keyed by `thread_id`. The `AgentState` is extended to carry an optional `image_base64` output field for image responses.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: langgraph ≥1.1.4, langchain ≥1.2.14, langchain-core ≥1.2.23, langgraph-checkpoint-sqlite (new), langchain-mcp-adapters (new), opik ≥1.0.0, fastmcp ≥2.0.0
**Storage**: SQLite via `langgraph-checkpoint-sqlite` (`SqliteSaver`) — stored at `./data/memory.db`, volume-mounted in Docker
**Testing**: pytest (to be added when tasks phase runs)
**Target Platform**: Local process / Docker container (same runtime as MCP server)
**Project Type**: Agentic service (long-running process)
**Performance Goals**: Response latency driven by LLM API + MCP tool calls; no hard numeric target
**Constraints**: Message list capped at 2 active messages after summarization; SQLite file must survive container restarts
**Scale/Scope**: Single-user sessions; multiple concurrent sessions differentiated by `thread_id`

## Constitution Check

The project constitution file is a blank template — no active principles or gates are defined. No violations to evaluate. This section will be re-checked after Phase 1 design if the constitution is populated.

## Project Structure

### Documentation (this feature)

```text
specs/001-langgraph-agent-design/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── agent-interface.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
├── agent/
│   ├── state.py          # AgentState — add image_base64 field
│   ├── prompts.py        # existing prompts (ROUTING, TOOL_USE, GENERAL)
│   ├── nodes.py          # router_node, tool_node, general_node, summarize_node
│   └── graph.py          # LangGraph graph definition + SqliteSaver checkpointer
├── services/
│   ├── mcp/              # existing FastMCP server (unchanged)
│   └── video/            # existing video processing (unchanged)
├── utils/
│   └── opik_config.py    # existing Opik setup (unchanged)
├── config.py             # add MEMORY_DB_PATH, AGENT_MODEL settings
└── main.py               # existing entry point (unchanged)

data/
└── memory.db             # SQLite checkpoint store (runtime, volume-mounted)
```

**Structure Decision**: Single project layout extending the existing `src/agent/` skeleton. No new top-level packages needed. All agent code lives in `src/agent/`; data directory holds the SQLite file at runtime.
