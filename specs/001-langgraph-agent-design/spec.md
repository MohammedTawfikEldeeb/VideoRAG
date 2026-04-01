# Feature Specification: VideoRAG LangGraph Agent

**Feature Branch**: `001-langgraph-agent-design`
**Created**: 2026-04-01
**Status**: Draft
**Input**: User description: "VideoRAG LangGraph agent with router, summarizer, SQLite checkpointing, and image output support"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a Question and Get a Video-Grounded Answer (Priority: P1)

A user sends a natural language question about a video. The agent determines whether the question requires querying the video tools (search, caption, clip extraction) or can be answered directly. If tools are needed, it invokes them and returns the answer — which may be a text response or a base64-encoded image frame.

**Why this priority**: This is the core interaction loop. Everything else (memory, summarization) supports this flow.

**Independent Test**: Can be tested end-to-end by sending a video question and verifying a relevant text or image response is returned.

**Acceptance Scenarios**:

1. **Given** a user asks "What happens at 2 minutes in the video?", **When** the router node evaluates the message, **Then** it routes to the tool-calling path and returns a grounded answer with optional image output.
2. **Given** a user asks "What is a neural network?", **When** the router evaluates the message, **Then** it routes to the general response path and answers directly without invoking any tools.
3. **Given** a tool returns an image result, **When** the agent assembles the response, **Then** the `image_base64` field in state is populated and returned to the user.

---

### User Story 2 - Persistent Multi-Turn Conversation Across Sessions (Priority: P2)

A user starts a conversation about a video in one session, closes the app, and resumes later. The agent restores the prior conversation context using a SQLite-backed checkpoint store keyed by `thread_id`, so the user does not need to re-explain what was previously discussed.

**Why this priority**: Without cross-session memory, users must repeat context on every new session — critical for long video analysis workflows.

**Independent Test**: Start a session, send 2-3 messages, restart with the same thread ID, and verify the agent recalls prior context without re-prompting.

**Acceptance Scenarios**:

1. **Given** a thread ID with prior messages in the checkpoint store, **When** the agent is initialized with that thread ID, **Then** prior conversation history is loaded and available to the agent.
2. **Given** a new thread ID, **When** the agent processes its first message, **Then** a new conversation record is created and persisted.
3. **Given** a conversation that spans multiple sessions, **When** the user asks a follow-up referencing earlier content, **Then** the agent responds accurately using the restored context.

---

### User Story 3 - Automatic Conversation Summarization (Priority: P3)

After 8 turns in a conversation, the agent automatically compresses the message history by summarizing older messages and retaining only the last 2 full messages. Each new summary extends the previous one so no context is lost over time.

**Why this priority**: Prevents unbounded message history growth during long video analysis sessions while preserving coherence.

**Independent Test**: Conduct a 10+ turn conversation and verify that the active message list stays at 2 after the threshold is crossed, while the summary field grows cumulatively.

**Acceptance Scenarios**:

1. **Given** a conversation with more than 10 messages in state, **When** the summarization condition is evaluated after a turn, **Then** the summarizer node is triggered.
2. **Given** an existing summary and new messages to compress, **When** the summarizer runs, **Then** the new summary extends the prior summary rather than replacing it.
3. **Given** the summarizer runs, **When** it completes, **Then** all messages except the last 2 are removed and the `summary` field in state is updated.
4. **Given** a fresh conversation with no prior summary, **When** the summarizer first triggers, **Then** a new summary is generated from all available messages above the retained 2.

---

### Edge Cases

- What happens when the router is uncertain whether a question requires tools or not?
- What happens if a tool call fails or returns no results — does the agent fall back to a graceful text response?
- What happens if the checkpoint store is unavailable or the database file is missing or corrupted?
- What happens when the user sends a message referencing a video that has not been indexed yet?
- What happens if image output is requested but the tool returns no image data?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The agent state MUST include: `messages` (append-only list), `summary` (string), `route_type` (boolean: `True` = tool call), `tool_results` (accumulating list of dicts), `turn_count` (incrementing integer), and `image_base64` (optional string for image responses).
- **FR-002**: The agent MUST include a router node that classifies each incoming user message as either requiring tool use or as a general question, and routes execution to the appropriate path.
- **FR-003**: The agent MUST support invocation of the three existing MCP tools (video search, frame captioning, clip extraction) from the tool-calling path.
- **FR-004**: The agent MUST include a summarizer node that is triggered when the message count in state exceeds 10, retains only the last 2 messages, and stores a cumulative summary in the `summary` field.
- **FR-005**: Each summarization cycle MUST extend the existing `summary` field rather than replace it, so full conversational context is preserved across multiple compression cycles.
- **FR-006**: The agent MUST use a SQLite-backed checkpoint store to persist conversation state, keyed by `thread_id`.
- **FR-007**: The checkpoint store MUST associate `thread_id` with the full message history and summary so conversations can be resumed across process restarts.
- **FR-008**: The agent MUST populate `image_base64` in state when a tool returns an image result, and include it in the response delivered to the user.
- **FR-009**: Prompts for the router node and any system-level guidance MUST be defined in a dedicated prompts module and injected into the relevant nodes at runtime.
- **FR-010**: The `turn_count` field MUST increment by 1 after each agent turn using a reducer function in the state definition.
- **FR-011**: The summarization trigger MUST be implemented as a conditional edge that evaluates message count and routes to either the summarizer node or continues to the end of the turn.

### Key Entities

- **AgentState**: The full in-flight state of a single conversation turn — includes messages, summary, routing decision, tool results, turn counter, and optional image output.
- **Conversation Thread**: A named session identified by `thread_id`, persisted in SQLite; contains the full checkpoint history of an ongoing or past conversation.
- **Summary**: A rolling, cumulative text record of all conversation history that has been compressed; extended (not replaced) on each summarization cycle.
- **Router Decision**: A binary classification (`tool_call` or `general`) made at the start of each turn to direct execution flow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The router correctly classifies tool-required vs. general questions in at least 90% of representative test cases.
- **SC-002**: After more than 10 turns, the active `messages` list in state never contains more than 2 messages, confirming summarization compression is working correctly.
- **SC-003**: A conversation resumed with a known `thread_id` recovers prior context and is reflected in the first response, with no re-explanation required from the user.
- **SC-004**: When a tool returns an image, `image_base64` is populated and the image is delivered to the user within the same response turn.
- **SC-005**: Cumulative summaries across 3 or more summarization cycles retain facts from early turns — verifiable by asking about early topics after many turns.

## Assumptions

- The existing MCP server with 3 tools (video search, frame captioning, clip extraction) is already running and accessible when the agent executes.
- The SQLite database file is stored at a persistent path (e.g., `./data/memory.db`) that survives process restarts; in Docker, this path is mounted as a volume.
- `thread_id` is supplied by the caller (e.g., a session ID or user identifier); the agent does not generate it internally.
- The summarizer uses the same LLM as the main agent — no separate summarization model is needed.
- `image_base64` is optional per turn; most responses will be text-only with `image_base64` left null.
- The existing `AgentState` in `src/agent/state.py` will be extended to add `image_base64: Optional[str]`; all other existing fields remain compatible.
- The agent runs as a long-running process (not serverless), so the SQLite connection can persist between turns within a session.
