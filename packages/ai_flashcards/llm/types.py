from dataclasses import  dataclass, field
from typing import Any

@dataclass
class ToolSpec:
    name: str
    description: str
    json_schema: dict[str, Any]


@dataclass
class AgentRequest:
    system_prompt: str
    user_prompt: str
    tools: list[ToolSpec] = field(default_factory=list)
    temperature: float = 0.2
    max_tokens: int = 800

@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]

@dataclass
class AgentResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None