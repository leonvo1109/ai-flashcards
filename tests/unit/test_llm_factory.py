"""Tests for ai_flashcards.llm.factory."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from ai_flashcards.llm import factory


def test_build_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        factory.build_provider({"provider": "bogus"})


def test_build_provider_google_requires_key(monkeypatch):
    """Avoid importing vendor google-genai stacks under tests (ABI / pydantic binaries)."""

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    stub = ModuleType("ai_flashcards.llm.providers.google_provider")

    class RaisesMissingGeminiKey:
        def __init__(self, **_kwargs: object) -> None:
            raise ValueError(
                "Missing Gemini API key (config.gemini_api_key or GOOGLE_API_KEY)."
            )

    setattr(stub, "GoogleProvider", RaisesMissingGeminiKey)

    monkeypatch.delitem(
        sys.modules, "ai_flashcards.llm.providers.google_provider", raising=False
    )
    monkeypatch.setitem(
        sys.modules, "ai_flashcards.llm.providers.google_provider", stub
    )

    with pytest.raises(ValueError, match="Missing Gemini API key"):
        factory.build_provider({"provider": "google", "gemini_api_key": "   "})


def test_build_provider_apple(monkeypatch):
    fake_instance = object()
    stub = MagicMock()
    stub.AppleProvider.return_value = fake_instance
    monkeypatch.setitem(
        sys.modules,
        "ai_flashcards.llm.providers.apple_provider",
        stub,
    )

    out = factory.build_provider({"provider": "apple"})

    assert out is fake_instance
    stub.AppleProvider.assert_called_once_with()
