"""Tests for ai_flashcards.card_hierarchy."""

from __future__ import annotations

import json

from ai_flashcards.card_hierarchy import CardHierarchyManager


def test_hierarchy_roundtrip_create_group_and_child(tmp_path):
    cfg = tmp_path / "cfg"
    hm = CardHierarchyManager(cfg)

    hm.create_group(10, group_name="G", group_description="D", group_tags=["t"])

    assert hm.add_card_to_group(10, 20) is True
    assert hm.get_parent_of_card(20) == 10
    assert 20 in hm.get_children_of_card(10)

    path = cfg / "hierarchy.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "10" in raw["parent_cards"]
    assert str(20) in raw["card_to_parent"]


def test_hierarchy_remove_card_from_group(tmp_path):
    hm = CardHierarchyManager(tmp_path / "cfg")
    hm.create_group(1)
    hm.add_card_to_group(1, 2)

    assert hm.remove_card_from_group(2) is True
    assert hm.get_parent_of_card(2) is None
