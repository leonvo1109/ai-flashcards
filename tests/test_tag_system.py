"""Tests for ai_flashcards.tag_system."""

from __future__ import annotations

import json

from ai_flashcards.tag_system import DeckTagStrategy, TagManager


def test_tag_manager_complete_tags_for_generated_card(tmp_path):
    tm = TagManager(tmp_path / "cfg")

    tags = tm.get_complete_tags_for_generated_card(
        "text", is_verified=False, is_variant=True
    )

    assert "ai_from_text" in tags
    assert "ai_needs_review" in tags
    assert "ai_generated" in tags
    assert "ai_variant" in tags
    assert "ai_single_info" in tags


def test_tag_manager_verified_uses_ai_verified(tmp_path):
    tm = TagManager(tmp_path / "cfg")

    assert tm.get_verification_tags(is_verified=True) == [
        "ai_verified",
        "ai_single_info",
    ]


def test_tag_manager_persists_custom_tag(tmp_path):
    cfg = tmp_path / "cfg"
    tm = TagManager(cfg)
    tm.add_custom_tag("ai_custom", "desc")

    tags_file = cfg / "tags.json"
    data = json.loads(tags_file.read_text(encoding="utf-8"))
    assert data["default_tags"]["ai_custom"] == "desc"

    tm2 = TagManager(cfg)
    assert tm2.get_tag_description("ai_custom") == "desc"


def test_deck_tag_strategy_parses_hierarchy():
    assert "subject_math" in DeckTagStrategy.get_deck_specific_tags(
        "Main::Math::Algebra"
    )
    assert "topic_algebra" in DeckTagStrategy.get_deck_specific_tags(
        "Main::Math::Algebra"
    )


def test_deck_tag_strategy_recommended_difficulty_by_back_length():
    tags = DeckTagStrategy.get_recommended_tags_for_card("q", "short back", "OnlyRoot")
    assert "difficulty_easy" in tags

    tags = DeckTagStrategy.get_recommended_tags_for_card(
        "q", " ".join(str(i) for i in range(15)), "OnlyRoot"
    )
    assert "difficulty_medium" in tags

    tags = DeckTagStrategy.get_recommended_tags_for_card(
        "q", " ".join(str(i) for i in range(40)), "OnlyRoot"
    )
    assert "difficulty_hard" in tags
