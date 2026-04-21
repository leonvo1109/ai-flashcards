import asyncio
from ..types import AgentRequest, AgentResponse
from ...lib.apple_fm_sdk import *


class AppleProvider:
    async def complete(self, req: AgentRequest) -> AgentResponse:

        model = SystemLanguageModel()
        is_available, reason = model.is_available()

        if is_available:
            session = LanguageModelSession(model=model)
            options = GenerationOptions(temperature=req.temperature,
                                        maximum_response_tokens=req.max_tokens)

            response = asyncio.run(
                session.respond(prompt=req.user_prompt, options=options)
            )
            return AgentResponse(text=response)
        else:
            raise ValueError(f"Modell nicht verfügbar: {reason}")
