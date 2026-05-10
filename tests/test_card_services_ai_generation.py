"""Integration-style tests for AI card generation / verification (real code paths, fake LLM)."""

from __future__ import annotations

import asyncio
import json

from ai_flashcards.card_services import (
    CardGenerationService,
    CardVerificationService,
    MultiTypeCards,
    _coerce_card_object_list,
    _extract_json_fragment_from_llm_text,
    _parse_json_embedded,
    _repair_common_json_issues,
    _text_field_from_card_dict,
)
from ai_flashcards.use_cases import SimpleRequest

from tests.support.fake_llm import FakeLLMProvider


def _run(coro):
    return asyncio.run(coro)


def test_fake_llm_records_generation_prompt_contains_source_and_context():
    raw_cards = json.dumps(
        [
            {"front": "Capital of France?", "back": "Paris", "tags": ["geo"]},
        ]
    )
    fake = FakeLLMProvider([f"```json\n{raw_cards}\n```"])
    svc = CardGenerationService(fake)

    deck_ctx = {"deck_name": "Geography", "model_names": ["Basic"]}
    cards = _run(svc.generate_from_text("France info.", deck_ctx, num_cards=1))

    assert len(fake.requests) == 1
    assert "France info." in fake.requests[0].user_prompt
    assert "Geography" in fake.requests[0].user_prompt
    assert len(cards) == 1
    assert cards[0]["front"] == "Capital of France?"
    assert cards[0]["back"] == "Paris"
    assert cards[0]["tags"] == ["geo"]


def test_generate_from_text_sentence_fallback_when_llm_invalid_json():
    fake = FakeLLMProvider(["not-json-{"])
    svc = CardGenerationService(fake)

    text = "First idea here. Second idea follows!"
    cards = _run(svc.generate_from_text(text, {}, num_cards=2))

    assert len(fake.requests) == 1
    assert len(cards) >= 1
    for c in cards:
        assert c["front"]
        assert c["back"]


def test_generate_from_image_text_uses_image_instructions_then_json():
    payload = json.dumps(
        [{"front": "Slide summary?", "back": "Key point.", "tags": []}]
    )
    fake = FakeLLMProvider([payload])
    svc = CardGenerationService(fake)

    deck_ctx = {"deck_name": "CS101"}
    cards = _run(
        svc.generate_from_image_text(
            "Bullet: recursion.", image_type="slide", deck_context=deck_ctx, num_cards=1
        )
    )

    assert len(fake.requests) == 1
    assert "presentation slides" in fake.requests[0].system_prompt.lower()
    assert "Bullet: recursion." in fake.requests[0].user_prompt
    assert cards[0]["back"] == "Key point."


def test_generate_from_image_text_retries_via_generate_from_text_on_first_failure():
    ok = json.dumps([{"front": "Q", "back": "A", "tags": []}])
    fake = FakeLLMProvider(["totally not json", ok])
    svc = CardGenerationService(fake)

    cards = _run(
        svc.generate_from_image_text(
            "Some OCR text.", "screenshot", {"deck_name": "X"}, 1
        )
    )

    assert len(fake.requests) == 2
    assert cards[0]["front"] == "Q"


def test_generate_multi_type_cards_accepts_cards_wrapped_and_trailing_commas():
    messy = """
Here's JSON:
```json
{"cards": [
  {"type": "def", "front": "What is X?", "back": "Y.", "rationale": "defs",},
]}
```
Thanks.
"""
    fake = FakeLLMProvider([messy])
    svc = CardVerificationService(fake)

    out = _run(
        svc.generate_multi_type_cards(
            "topic front",
            "topic back",
            {"deck_name": "Deck"},
            original_card_id=42,
        )
    )

    assert isinstance(out, MultiTypeCards)
    assert out.original_card_id == 42
    assert len(out.cards) == 1
    assert out.cards[0]["type"] == "def"
    assert out.cards[0]["front"] == "What is X?"
    assert out.cards[0]["back"] == "Y."
    assert out.cards[0]["rationale"] == "defs"


def test_generate_multi_type_cards_question_answer_aliases():
    body = json.dumps(
        [
            {
                "type": "reverse",
                "question": "Term?",
                "answer": "Meaning.",
                "explanation": "synonym field",
            }
        ]
    )
    fake = FakeLLMProvider([body])
    svc = CardVerificationService(fake)

    out = _run(svc.generate_multi_type_cards("f", "b", {}))

    assert len(out.cards) == 1
    assert out.cards[0]["front"] == "Term?"
    assert out.cards[0]["back"] == "Meaning."


def test_verify_card_skips_replacement_when_valid_json_ok():
    verdict = json.dumps(
        {
            "is_valid": True,
            "issues": [],
            "violations": {"single_info_principle": False},
            "suggestions": [],
        }
    )
    fake = FakeLLMProvider([verdict])
    svc = CardVerificationService(fake)

    result = _run(svc.verify_card("Front", "Back", {"deck_name": "D"}))

    assert result.is_valid is True
    assert result.suggested_improvements == []
    assert len(fake.requests) == 1


def test_verify_card_requests_single_info_cards_when_invalid():
    verdict = json.dumps(
        {
            "is_valid": False,
            "issues": ["too broad"],
            "violations": {"single_info_principle": False},
            "suggestions": [],
        }
    )
    replacements = json.dumps(
        [
            {
                "front": "f1",
                "back": "b1",
                "concept": "c1",
            }
        ]
    )
    fake = FakeLLMProvider([verdict, replacements])
    svc = CardVerificationService(fake)

    result = _run(svc.verify_card("Wide front", "Wide back", {}))

    assert result.is_valid is False
    assert len(fake.requests) == 2
    assert len(result.suggested_improvements) == 1
    assert result.suggested_improvements[0]["front"] == "f1"


def test_simple_request_ask_returns_llm_text():
    fake = FakeLLMProvider(["hello"])
    req = SimpleRequest(fake)

    assert _run(req.ask("ping")) == "hello"
    assert fake.requests[0].user_prompt == "ping"


def test_json_helpers_mirror_multi_type_pipeline():
    wrapped = _extract_json_fragment_from_llm_text(
        'noise ```json\n[{"front":"a","back":"b"}]\n``` tail'
    )
    parsed = _parse_json_embedded(wrapped)
    cards = _coerce_card_object_list(parsed or [])
    assert len(cards) == 1

    repaired = _repair_common_json_issues('[{"front":"x","back":"y",}]')
    parsed2 = _parse_json_embedded(repaired)
    assert isinstance(parsed2, list)

    assert (
        _text_field_from_card_dict(
            {"Question": "Q?", "Answer": "A!"}, "question", "answer"
        )
        == "Q?"
    )


def test_coerce_card_object_list_prefers_cards_key_then_dict_fallback():
    with_cards = {"cards": [{"front": "1", "back": "a"}]}
    assert len(_coerce_card_object_list(with_cards)) == 1

    fallback_only = {"variant_a": {"front": "x", "back": "y"}}
    lst = _coerce_card_object_list(fallback_only)
    assert len(lst) == 1
    assert lst[0].get("front") == "x"


def test_generate_multi_type_cards_accepts_flashcards_key_and_nested_card():
    body = json.dumps(
        {
            "flashcards": [
                {
                    "type": "app",
                    "card": {"front": "Use case?", "back": "Example."},
                }
            ]
        }
    )
    fake = FakeLLMProvider([body])
    svc = CardVerificationService(fake)

    out = _run(svc.generate_multi_type_cards("f", "b", {}))

    assert len(out.cards) == 1
    assert out.cards[0]["type"] == "app"
    assert out.cards[0]["front"] == "Use case?"
    assert out.cards[0]["back"] == "Example."
