"""Tests for Gemini (`google-genai`) provider."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from ai_flashcards.llm import factory
from ai_flashcards.llm.providers.google_provider import DEFAULT_GEMINI_MODEL, GoogleProvider
from ai_flashcards.llm.types import AgentRequest


def test_google_provider_complete_runs_generate_in_thread():
    mock_response = MagicMock()
    mock_response.text = "ok"

    mock_models = MagicMock()
    mock_models.generate_content.return_value = mock_response

    mock_client = MagicMock()
    mock_client.models = mock_models

    with patch(
        "ai_flashcards.llm.providers.google_provider.genai.Client",
        return_value=mock_client,
    ):
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        async def run():
            return await provider.complete(
                AgentRequest(system_prompt="sys", user_prompt="user", max_tokens=100)
            )

        out = asyncio.run(run())

    assert out.text == "ok"
    mock_models.generate_content.assert_called_once()
    call_kw = mock_models.generate_content.call_args.kwargs
    assert call_kw["model"] == "gemini-2.0-flash"
    assert call_kw["contents"] == "user"
    cfg = call_kw["config"]
    assert cfg.system_instruction == "sys"
    assert cfg.max_output_tokens == 100


def test_google_provider_empty_model_falls_back_to_default():
    with patch("ai_flashcards.llm.providers.google_provider.genai.Client"):
        p = GoogleProvider(api_key="k", model="   ")
    assert p._model == DEFAULT_GEMINI_MODEL


def test_build_provider_resolves_empty_model_string(monkeypatch):
    captured: dict[str, str] = {}

    class FakeGoogle:
        def __init__(self, *, api_key: str, model: str) -> None:
            captured["api_key"] = api_key
            captured["model"] = model

    monkeypatch.setattr(
        "ai_flashcards.llm.providers.google_provider.GoogleProvider",
        FakeGoogle,
    )
    factory.build_provider(
        {"provider": "google", "gemini_api_key": "secret", "model": ""}
    )
    assert captured["model"] == DEFAULT_GEMINI_MODEL
    assert captured["api_key"] == "secret"
