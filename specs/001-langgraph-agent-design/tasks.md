# Tasks: VideoRAG LangGraph Agent

**Input**: Design documents from `/specs/001-langgraph-agent-design/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the single new dependency and protect runtime data from accidental commits.

- [X] T001 Add `langgraph-checkpoint-sqlite>=2.0` to `dependencies` in `pyproject.toml`
- [X] T002 [P] Add `data/` and `data/*.db` entries to `.gitignore` to prevent committing the SQLite checkpoint database

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core state, configuration, and tool definitions that every user story depends on. Must be complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add `MEMORY_DB_PATH: str = "./data/memory.db"`, `AGENT_MODEL: str = "openai/gpt-4o-mini"`, and `ROUTER_MODEL: str = "openai/gpt-4o-mini"` to the `Settings` class in `src/config.py`
- [X] T004 Add `image_base64: Optional[str]` field with `last-write` semantics (no reducer) to `AgentState` in `src/agent/state.py`; add `from typing import Optional` import
- [X] T005 [P] Create `src/agent/tools.py` with four LangChain `@tool`-decorated wrappers: `process_video`, `get_video_clip_from_user_query`, `get_video_clip_from_image`, and `ask_question_about_video`; each delegates directly to the corresponding function in `src/services/` (same logic as `src/services/mcp/tools.py` but using LangChain's `@tool` decorator from `langchain_core.tools`)

**Checkpoint**: `AgentState` has `image_base64`, config has three new fields, and `src/agent/tools.py` exposes four callable tools — user story implementation can now begin.

---

## Phase 3: User Story 1 — Ask a Question, Get a Video-Grounded Answer (Priority: P1) 🎯 MVP

**Goal**: A user message is routed to either a tool-calling path (video tools) or a general response path, and the agent returns a text answer with an optional `image_base64` frame from any extracted clip.

**Independent Test**: Invoke `graph.invoke({"messages": [HumanMessage(content="What happens at 2:00?")]}, config)` and verify `result["messages"][-1]` is an `AIMessage` with content. Invoke with a non-video question and verify no tools are called.

### Implementation for User Story 1

- [X] T006 [US1] Implement `router_node(state: AgentState) -> dict` in `src/agent/nodes.py`: build an LLM call using `settings.ROUTER_MODEL` (via OpenRouter), pass `ROUTING_SYSTEM_PROMPT` as system message plus `state["messages"]`, use structured output (`with_structured_output(bool)` or JSON mode) to obtain the routing boolean, return `{"route_type": bool_result}`
- [X] T007 [P] [US1] Implement `general_node(state: AgentState) -> dict` in `src/agent/nodes.py`: build an LLM call using `settings.AGENT_MODEL`, prepend `GENERAL_SYSTEM_PROMPT` as system message, call `llm.invoke(state["messages"])`, return `{"messages": [response], "turn_count": 1}`
- [X] T008 [US1] Implement `tool_node(state: AgentState) -> dict` in `src/agent/nodes.py`: build an LLM call using `settings.AGENT_MODEL` with all four tools from `src/agent/tools.py` bound via `llm.bind_tools(tools)`, pass `TOOL_USE_SYSTEM_PROMPT` formatted with `is_image_provided` flag (check if `state.get("image_base64")` is not None), execute tool calls from the LLM response, for any tool result that is a file path ending in `.mp4` read the first video frame as base64 using moviepy and set as `image_base64`, return `{"messages": [response], "tool_results": [{"tool_name": ..., "result": ...}], "image_base64": <base64 or None>, "turn_count": 1}`
- [X] T009 [US1] Implement `route_decision(state: AgentState) -> str` in `src/agent/graph.py`: return `"tool_node"` if `state["route_type"]` is `True`, else `"general_node"`
- [X] T010 [US1] Build the initial graph in `src/agent/graph.py`: create `StateGraph(AgentState)`, add nodes (`router_node`, `tool_node`, `general_node`), set `START → router_node`, add conditional edge from `router_node` using `route_decision` mapping to `{"tool_node": "tool_node", "general_node": "general_node"}`, add edges from both `tool_node` and `general_node` to `END`; expose `build_graph() -> CompiledStateGraph` factory function that compiles and returns the graph

**Checkpoint**: `build_graph()` can be imported and invoked. Routing works. Tool calls execute. Text and image responses are returned. US1 is fully functional without persistence or summarization.

---

## Phase 4: User Story 2 — Persistent Multi-Turn Conversation Across Sessions (Priority: P2)

**Goal**: Conversations persist across process restarts via SQLite. Providing the same `thread_id` in a new session restores full prior context.

**Independent Test**: Invoke the graph twice in separate Python sessions using the same `thread_id`, sending a follow-up question in the second session that references content from the first. Verify the agent answers coherently without being re-told the context.

### Implementation for User Story 2

- [X] T011 [US2] Update `build_graph()` in `src/agent/graph.py`: import `SqliteSaver` from `langgraph.checkpoint.sqlite`, auto-create the directory with `Path(settings.MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)`, initialize `SqliteSaver.from_conn_string(settings.MEMORY_DB_PATH)` as `checkpointer`, pass it to `builder.compile(checkpointer=checkpointer)`, and document that callers must pass `config={"configurable": {"thread_id": "<id>"}}` to every `graph.invoke()` call
- [ ] T012 [P] [US2] Add `data/` volume mount to `docker-compose.yml`: add `./data:/app/data` under the service's `volumes` list and add `MEMORY_DB_PATH=/app/data/memory.db` to the service's `environment` block

**Checkpoint**: SQLite checkpoint store is active. Conversations resume across restarts. Docker persists the database file to the host. US2 is fully functional.

---

## Phase 5: User Story 3 — Automatic Conversation Summarization (Priority: P3)

**Goal**: After more than 10 messages accumulate, the agent compresses them into a rolling summary and retains only the last 2 messages. Each summarization cycle extends the prior summary so no context is lost.

**Independent Test**: Run a 12-turn conversation. After turn 11, verify `len(result["messages"]) == 2` and `result["summary"]` is a non-empty string. Run a second 10-turn conversation starting from the same `thread_id` and verify the new summary extends the first one.

### Implementation for User Story 3

- [X] T013 [US3] Add summary injection to `router_node`, `tool_node`, and `general_node` in `src/agent/nodes.py`: before each LLM call, check `summary = state.get("summary", "")`, and if non-empty prepend `SystemMessage(content=f"Summary of prior conversation:\n{summary}")` to the messages list passed to the LLM (do not mutate `state["messages"]` — build a local list for the call only)
- [X] T014 [US3] Implement `summarize_node(state: AgentState) -> dict` in `src/agent/nodes.py`: build the summarization prompt — if `state["summary"]` exists use `f"This is the current summary: {state['summary']}\n\nExtend it with the new messages above."`, else use `"Summarise the conversation above in a few sentences."`; append the prompt as a `HumanMessage` to `state["messages"]`; invoke the LLM; compute `delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]`; return `{"summary": response.content, "messages": delete_messages}`
- [X] T015 [US3] Implement `should_summarise(state: AgentState) -> str` in `src/agent/graph.py`: return `"summarise"` if `len(state["messages"]) > 10`, else `"continue"`
- [X] T016 [US3] Wire summarization into the graph in `src/agent/graph.py`: add `summarize_node` to the graph, replace the direct `tool_node → END` and `general_node → END` edges with `add_conditional_edges("tool_node", should_summarise, {"summarise": "summarize_node", "continue": END})` and the same for `general_node`; add `builder.add_edge("summarize_node", END)`

**Checkpoint**: All three user stories are fully functional. Conversations compress automatically after 10 messages. Summaries accumulate across cycles. US3 is complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Observability, clean public API, and end-to-end validation.

- [X] T017 [P] Add Opik tracing support in `src/agent/graph.py`: import `OpikTracer` from `opik.integrations.langchain`; update `build_graph()` docstring to note that callers can add Opik tracing by passing `config={"configurable": {"thread_id": "..."}, "callbacks": [OpikTracer()]}` to `graph.invoke()`; the existing `opik_config.py` initialization at startup is sufficient — no additional wiring needed
- [X] T018 [P] Export `build_graph` and `AgentState` from `src/agent/__init__.py` so external code can import via `from src.agent import build_graph, AgentState`
- [X] T019 [P] Manually validate the complete flow against `specs/001-langgraph-agent-design/quickstart.md`: run a basic query (US1), restart and resume session (US2), conduct 12-turn conversation to trigger summarization (US3); confirm `image_base64` is populated on clip extraction turns

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T001 and T002 are independent [P]
- **Foundational (Phase 2)**: Requires Phase 1 completion — **BLOCKS all user stories**; T003 and T004 are sequential (both touch `src/config.py` / `src/agent/state.py`); T005 [P] can run alongside T003/T004
- **User Story Phases (3–5)**: All depend on Phase 2 completion; can proceed in priority order or in parallel if multiple developers
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependency on US2 or US3 — independently testable after Phase 2
- **US2 (P2)**: No dependency on US3 — adds checkpointer to existing graph without modifying nodes
- **US3 (P3)**: Modifies nodes and graph wiring built in US1 — can be developed independently but completes the graph

### Within Each User Story

- US1: T006 (router) and T007 (general) can run in parallel [P]; T008 (tool) depends on T005 [P]; T009 depends on T006; T010 depends on T006–T009
- US2: T011 and T012 are independent [P]
- US3: T013 → T014 → T015 → T016 (sequential: each step builds on the previous)

### Parallel Opportunities

- T001 ‖ T002 (Phase 1)
- T003 ‖ T005 (Phase 2, T004 after T003)
- T006 ‖ T007 (Phase 3)
- T011 ‖ T012 (Phase 4)
- T017 ‖ T018 ‖ T019 (Phase 6)

---

## Parallel Example: User Story 1

```bash
# Run in parallel after T005 completes:
Task T006: Implement router_node in src/agent/nodes.py
Task T007: Implement general_node in src/agent/nodes.py

# After T006 + T007 + T008 complete:
Task T009: Implement route_decision in src/agent/graph.py
Task T010: Build graph skeleton in src/agent/graph.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T005) — CRITICAL
3. Complete Phase 3: User Story 1 (T006–T010)
4. **STOP and VALIDATE**: `build_graph().invoke({"messages": [HumanMessage("What is in this video?")]}, {"configurable": {"thread_id": "test"}})` returns a valid `AIMessage`
5. Demo routing (tool vs. general) and image output

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 complete → routing, tools, image output working (MVP)
3. US2 complete → sessions persist across restarts
4. US3 complete → long conversations stay within context limits
5. Polish → observability and clean public API

### Parallel Team Strategy

With two developers after Phase 2:
- Developer A: US1 (T006–T010)
- Developer B: US2 (T011–T012) — can start immediately since it only wraps the compiled graph

---

## Notes

- [P] tasks = different files, no shared state dependencies
- [Story] label maps each task to a specific user story for traceability
- `src/agent/nodes.py` is touched by multiple phases — coordinate carefully if working in parallel
- T013 (summary injection) modifies nodes created in Phase 3 — this is intentional; US3 enriches rather than replaces US1 node behavior
- The `data/` directory is runtime-only; never commit `memory.db`
- Validate against `quickstart.md` after each phase checkpoint
