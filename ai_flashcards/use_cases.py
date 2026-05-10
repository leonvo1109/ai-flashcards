from dataclasses import dataclass

from .llm.base import LLMProvider
from .llm.types import AgentRequest


@dataclass
class SimpleRequest:
    provider: LLMProvider

    async def ask(
        self, user_prompt: str, system_prompt: str = "You are a helpful assistant."
    ) -> str:
        request = AgentRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        response = await self.provider.complete(request)
        return response.text
