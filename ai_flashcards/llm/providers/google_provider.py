import asyncio
import os

from google import genai
from google.genai.types import GenerateContentConfig

from ..gemini_config import DEFAULT_GEMINI_MODEL
from ..types import AgentRequest, AgentResponse


class GoogleProvider:
    """Gemini via `google-genai` (sync HTTP API wrapped for async callers)."""

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL) -> None:
        key = api_key.strip() or os.getenv("GOOGLE_API_KEY", "").strip()
        if not key:
            raise ValueError(
                "Missing Gemini API key (config.gemini_api_key or GOOGLE_API_KEY)."
            )
        self._client = genai.Client(api_key=key)
        self._model = (model or "").strip() or DEFAULT_GEMINI_MODEL

    async def complete(self, req: AgentRequest) -> AgentResponse:
        config = GenerateContentConfig(
            temperature=req.temperature,
            system_instruction=req.system_prompt,
            max_output_tokens=req.max_tokens,
        )

        # google-genai uses blocking HTTP; avoid freezing Anki's asyncio event loop.
        def _generate():
            return self._client.models.generate_content(
                model=self._model,
                contents=req.user_prompt,
                config=config,
            )

        response = await asyncio.to_thread(_generate)
        raw = getattr(response, "text", None)
        text = raw if isinstance(raw, str) else ""
        return AgentResponse(text=text)
