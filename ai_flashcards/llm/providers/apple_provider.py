from ..types import AgentRequest, AgentResponse
from ...lib.apple_fm_sdk import *


class AppleProvider:
    async def complete(self, req: AgentRequest) -> AgentResponse:

        model = SystemLanguageModel()
        is_available, reason = model.is_available()

        if is_available:
            session = LanguageModelSession(model=model)
            options = GenerationOptions(
                temperature=req.temperature, maximum_response_tokens=req.max_tokens
            )

            sys = (req.system_prompt or "").strip()
            user = (req.user_prompt or "").strip()
            prompt = f"{sys}\n\n{user}" if sys else user

            response = await session.respond(prompt=prompt, options=options)
            text = response if isinstance(response, str) else str(response or "")
            return AgentResponse(text=text)
        else:
            raise ValueError(f"Modell nicht verfügbar: {reason}")
