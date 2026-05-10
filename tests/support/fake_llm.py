"""In-memory LLM stub so AI flows stay deterministic without live APIs."""

from __future__ import annotations

from collections.abc import Callable

from ai_flashcards.llm.types import AgentRequest, AgentResponse


class FakeLLMProvider:
    """Records prompts and returns canned responses in order."""

    def __init__(
        self,
        responses: list[str | AgentResponse],
        *,
        side_effect: Callable[[AgentRequest], AgentResponse] | None = None,
    ) -> None:
        self.requests: list[AgentRequest] = []
        self._queue = list(responses)
        self._side_effect = side_effect

    async def complete(self, req: AgentRequest) -> AgentResponse:
        self.requests.append(req)
        if self._side_effect is not None:
            return self._side_effect(req)
        if not self._queue:
            msg = "FakeLLMProvider has no canned response left"
            raise RuntimeError(msg)
        r = self._queue.pop(0)
        return r if isinstance(r, AgentResponse) else AgentResponse(text=r)
