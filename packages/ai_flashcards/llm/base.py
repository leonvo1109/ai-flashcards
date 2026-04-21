from typing import Protocol
from .types import AgentRequest, AgentResponse

class LLMProvider(Protocol):
    async def complete(self, req: AgentRequest) -> AgentResponse: ...