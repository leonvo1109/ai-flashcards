import os
from google import genai
from google.genai.types import GenerateContentConfig
from ..types import AgentRequest, AgentResponse


class GoogleProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        key = api_key.strip() or os.getenv("GOOGLE_API_KEY", "").strip()
        if not key:
            raise ValueError(
                "Missing Gemini API key (config.gemini_api_key or GOOGLE_API_KEY)."
            )
        self._client = genai.Client(api_key=key)
        self._model = model

    async def complete(self, req: AgentRequest) -> AgentResponse:
        config = GenerateContentConfig(
            temperature=req.temperature,
            system_instruction=req.system_prompt,
            max_output_tokens=req.max_tokens,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=req.user_prompt,
            config=config,
        )
        raw = getattr(response, "text", None)
        text = raw if isinstance(raw, str) else ""
        return AgentResponse(text=text)
