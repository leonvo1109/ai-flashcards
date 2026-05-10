"""Card hierarchy and grouping system for managing related cards."""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import json


@dataclass
class CardGroup:
    """Represents a group of related cards that stem from one parent card."""

    parent_card_id: int  # The original/seed card
    generated_card_ids: list[int] = field(
        default_factory=list
    )  # Cards generated from parent
    group_tags: list[str] = field(default_factory=list)  # Tags for the group
    group_name: str = ""  # Human-readable name
    group_description: str = ""  # What makes this group coherent
    created_at: float = 0.0  # Timestamp


@dataclass
class HierarchyMetadata:
    """Stores metadata about card hierarchy and groups."""

    parent_cards: dict[int, CardGroup] = field(
        default_factory=dict
    )  # parent_id -> CardGroup
    card_to_parent: dict[int, int] = field(default_factory=dict)  # card_id -> parent_id


class CardHierarchyManager:
    """Manages the hierarchy and grouping of cards."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.hierarchy_file = self.config_dir / "hierarchy.json"
        self.hierarchy = self._load_hierarchy()

    def _load_hierarchy(self) -> HierarchyMetadata:
        """Load hierarchy metadata from file."""
        if self.hierarchy_file.exists():
            try:
                with open(self.hierarchy_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    metadata = HierarchyMetadata()

                    # Reconstruct parent cards
                    for parent_id_str, group_data in data.get(
                        "parent_cards", {}
                    ).items():
                        parent_id = int(parent_id_str)
                        group = CardGroup(
                            parent_card_id=parent_id,
                            generated_card_ids=group_data.get("generated_card_ids", []),
                            group_tags=group_data.get("group_tags", []),
                            group_name=group_data.get("group_name", ""),
                            group_description=group_data.get("group_description", ""),
                            created_at=group_data.get("created_at", 0.0),
                        )
                        metadata.parent_cards[parent_id] = group

                    # Reconstruct reverse mapping
                    for card_id_str, parent_id in data.get(
                        "card_to_parent", {}
                    ).items():
                        metadata.card_to_parent[int(card_id_str)] = parent_id

                    return metadata
            except Exception as e:
                print(f"Error loading hierarchy: {e}")

        return HierarchyMetadata()

    def _save_hierarchy(self) -> None:
        """Save hierarchy metadata to file."""
        try:
            data = {
                "parent_cards": {},
                "card_to_parent": {},
            }

            # Convert parent_cards
            for parent_id, group in self.hierarchy.parent_cards.items():
                data["parent_cards"][str(parent_id)] = {
                    "generated_card_ids": group.generated_card_ids,
                    "group_tags": group.group_tags,
                    "group_name": group.group_name,
                    "group_description": group.group_description,
                    "created_at": group.created_at,
                }

            # Convert card_to_parent
            for card_id, parent_id in self.hierarchy.card_to_parent.items():
                data["card_to_parent"][str(card_id)] = parent_id

            with open(self.hierarchy_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving hierarchy: {e}")

    def create_group(
        self,
        parent_card_id: int,
        group_name: str = "",
        group_description: str = "",
        group_tags: list[str] | None = None,
    ) -> None:
        """Create a new card group with a parent card."""
        import time

        group = CardGroup(
            parent_card_id=parent_card_id,
            generated_card_ids=[],
            group_tags=group_tags or [],
            group_name=group_name,
            group_description=group_description,
            created_at=time.time(),
        )

        self.hierarchy.parent_cards[parent_card_id] = group
        self._save_hierarchy()

    def add_card_to_group(self, parent_card_id: int, generated_card_id: int) -> bool:
        """Add a generated card to a parent card's group."""
        if parent_card_id not in self.hierarchy.parent_cards:
            return False

        group = self.hierarchy.parent_cards[parent_card_id]
        if generated_card_id not in group.generated_card_ids:
            group.generated_card_ids.append(generated_card_id)

        self.hierarchy.card_to_parent[generated_card_id] = parent_card_id
        self._save_hierarchy()
        return True

    def get_group(self, parent_card_id: int) -> Optional[CardGroup]:
        """Get a card group by parent card ID."""
        return self.hierarchy.parent_cards.get(parent_card_id)

    def get_parent_of_card(self, card_id: int) -> Optional[int]:
        """Get the parent card ID of a given card, or None if not part of a group."""
        return self.hierarchy.card_to_parent.get(card_id)

    def get_children_of_card(self, parent_card_id: int) -> list[int]:
        """Get all generated cards under a parent card."""
        group = self.hierarchy.parent_cards.get(parent_card_id)
        return group.generated_card_ids if group else []

    def remove_card_from_group(self, card_id: int) -> bool:
        """Remove a card from its group."""
        parent_id = self.hierarchy.card_to_parent.get(card_id)
        if parent_id is None:
            return False

        group = self.hierarchy.parent_cards.get(parent_id)
        if group and card_id in group.generated_card_ids:
            group.generated_card_ids.remove(card_id)

        del self.hierarchy.card_to_parent[card_id]
        self._save_hierarchy()
        return True

    def update_group_metadata(
        self,
        parent_card_id: int,
        group_name: Optional[str] = None,
        group_description: Optional[str] = None,
        group_tags: Optional[list[str]] = None,
    ) -> bool:
        """Update metadata for a card group."""
        group = self.hierarchy.parent_cards.get(parent_card_id)
        if not group:
            return False

        if group_name is not None:
            group.group_name = group_name

        if group_description is not None:
            group.group_description = group_description

        if group_tags is not None:
            group.group_tags = group_tags

        self._save_hierarchy()
        return True

    def get_all_parent_cards(self) -> list[int]:
        """Get all parent card IDs."""
        return list(self.hierarchy.parent_cards.keys())

    def get_groups_summary(self) -> dict:
        """Get a summary of all groups."""
        summary = {}
        for parent_id, group in self.hierarchy.parent_cards.items():
            summary[parent_id] = {
                "group_name": group.group_name,
                "description": group.group_description,
                "child_count": len(group.generated_card_ids),
                "tags": group.group_tags,
            }
        return summary
