from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
import operator
from pydantic import BaseModel

class AgentState(TypedDict):
    messages: str = Annotated[list, add_messages]
    summary: str
    route_type: bool  # True for tool call
    tool_results: Annotated[list[dict], operator.add]
    turn_count: Annotated[int, lambda a, b: a + b]  # reducer to increment after every turn
    image_base64: Optional[str]  # Base64-encoded image string for visual results


class RouterOutput(BaseModel):
    requires_tools: bool