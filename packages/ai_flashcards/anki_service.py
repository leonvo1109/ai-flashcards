"""Service for interacting with Anki database and card management."""

from dataclasses import dataclass
from typing import Any, Optional

from anki.decks import DeckId
from aqt import mw


@dataclass
class CardInfo:
    """Information about an Anki card."""

    card_id: int
    note_id: int
    front: str
    back: str
    deck_name: str
    model_name: str
    tags: list[str]


@dataclass
class DeckInfo:
    """Information about an Anki deck including its structure."""

    name: str
    description: str
    note_types: list[str]


class AnkiService:
    """Service for accessing Anki data."""

    @staticmethod
    def deck_name_for_did(deck_id: int | None) -> str:
        """Resolve deck name from a card's deck id (modern col.decks API)."""
        if not mw.col or deck_id is None:
            return ""
        try:
            d = mw.col.decks.get_legacy(DeckId(int(deck_id)))
            if d:
                return str(d.get("name") or "")
        except Exception:
            pass
        return ""

    @staticmethod
    def get_last_card() -> Optional[CardInfo]:
        """Get the last added or viewed card from the current deck."""
        if not mw.col:
            return None

        # Get cards sorted by last modification time (newest first)
        try:
            # Empty search is brittle; "*" matches all cards (Anki card search syntax).
            cards = mw.col.find_cards("*", order=True)
            if not cards:
                return None

            card_id = cards[0]
            card = mw.col.get_card(card_id)
            note = card.note()

            return CardInfo(
                card_id=card_id,
                note_id=note.id,
                front=note["Front"] if "Front" in note else "",
                back=note["Back"] if "Back" in note else "",
                deck_name=AnkiService.deck_name_for_did(card.did),
                model_name=note.model()["name"],
                tags=note.tags,
            )
        except Exception as e:
            print(f"Error getting last card: {e}")
            return None

    @staticmethod
    def get_card_by_id(card_id: int) -> Optional[CardInfo]:
        """Get card information by card ID."""
        if not mw.col:
            return None

        try:
            card = mw.col.get_card(card_id)
            note = card.note()

            return CardInfo(
                card_id=card_id,
                note_id=note.id,
                front=note.get("Front", ""),
                back=note.get("Back", ""),
                deck_name=AnkiService.deck_name_for_did(card.did),
                model_name=note.model()["name"],
                tags=note.tags,
            )
        except Exception as e:
            print(f"Error getting card {card_id}: {e}")
            return None

    @staticmethod
    def search_cards(query: str) -> list[int]:
        """Search for cards using Anki search syntax."""
        if not mw.col:
            return []

        try:
            return mw.col.find_cards(query)
        except Exception as e:
            print(f"Error searching cards: {e}")
            return []

    @staticmethod
    def get_recent_cards(limit: int = 100) -> list[int]:
        """Return recent card IDs for selection UI.

        Uses the collection DB directly so we avoid brittle search queries like "".
        """
        if not mw.col:
            return []

        try:
            db = mw.col.db
            try:
                return [
                    int(card_id)
                    for card_id in db.list(
                        "select id from cards order by mod desc limit ?", limit
                    )
                ]
            except Exception:
                # Fallback for DB wrappers that support all() instead of list()
                rows = db.all("select id from cards order by mod desc limit ?", limit)
                return [int(row[0]) for row in rows]
        except Exception as e:
            print(f"Error getting recent cards: {e}")
            return []

    @staticmethod
    def get_all_decks() -> list[DeckInfo]:
        """Get information about all available decks."""
        if not mw.col:
            return []

        try:
            deck_infos = []
            for deck_dict in mw.col.decks.all():
                note_types = []
                try:
                    # Get note types used in this deck
                    cards_in_deck = mw.col.find_cards(f"deck:\"{deck_dict['name']}\"")
                    if cards_in_deck:
                        note_types_set = set()
                        for card_id in cards_in_deck[:20]:  # Sample first 20
                            card = mw.col.get_card(card_id)
                            note_types_set.add(card.note().model()["name"])
                        note_types = list(note_types_set)
                except Exception:
                    pass

                deck_infos.append(
                    DeckInfo(
                        name=deck_dict["name"],
                        description=deck_dict.get("desc", ""),
                        note_types=note_types,
                    )
                )

            return deck_infos
        except Exception as e:
            print(f"Error getting decks: {e}")
            return []

    @staticmethod
    def get_first_card_id_for_note(note_id: int) -> Optional[int]:
        """Return one card id belonging to the note (for tagging after note creation)."""
        if not mw.col:
            return None
        try:
            cid = mw.col.db.scalar(
                "select id from cards where nid = ? order by id limit 1", note_id
            )
            return int(cid) if cid is not None else None
        except Exception as e:
            print(f"Error resolving card for note {note_id}: {e}")
            return None

    @staticmethod
    def add_card(
        front: str,
        back: str,
        deck_name: str,
        model_name: str = "Basic",
        tags: list[str] | None = None,
    ) -> Optional[int]:
        """Add a new card to Anki.

        Returns the note ID if successful, None otherwise.
        """
        if not mw.col:
            return None

        try:
            # Get the model
            models = mw.col.models.byName(model_name)
            if not models:
                print(f"Model '{model_name}' not found")
                return None

            model = models

            # Create a new note
            note = mw.col.new_note(model)
            note["Front"] = front
            note["Back"] = back

            if tags:
                note.tags = tags

            # Get the deck
            deck = mw.col.decks.byName(deck_name)
            if not deck:
                # Create the deck if it doesn't exist
                deck = mw.col.decks.id(deck_name)

            # Add the note
            mw.col.add_note(note, deck)

            return note.id
        except Exception as e:
            print(f"Error adding card: {e}")
            return None

    @staticmethod
    def add_cards_batch(
        cards: list[dict[str, str]],
        deck_name: str,
        model_name: str = "Basic",
    ) -> list[int]:
        """Add multiple cards at once.

        Each card dict should have 'front', 'back', and optional 'tags' keys.
        Returns list of added note IDs.
        """
        if not mw.col:
            return []

        note_ids = []
        try:
            for card_data in cards:
                note_id = AnkiService.add_card(
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    deck_name=deck_name,
                    model_name=model_name,
                    tags=card_data.get("tags", []),
                )
                if note_id:
                    note_ids.append(note_id)

            return note_ids
        except Exception as e:
            print(f"Error adding cards batch: {e}")
            return note_ids

    @staticmethod
    def update_card(
        card_id: int,
        front: Optional[str] = None,
        back: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Update an existing card."""
        if not mw.col:
            return False

        try:
            card = mw.col.get_card(card_id)
            note = card.note()

            if front is not None:
                note["Front"] = front

            if back is not None:
                note["Back"] = back

            if tags is not None:
                note.tags = tags

            mw.col.update_note(note)
            return True
        except Exception as e:
            print(f"Error updating card: {e}")
            return False

    @staticmethod
    def add_tags_to_card(card_id: int, tags: list[str]) -> bool:
        """Add tags to a card."""
        if not mw.col:
            return False

        try:
            card = mw.col.get_card(card_id)
            note = card.note()

            # Add new tags without replacing existing ones
            existing_tags = set(note.tags)
            existing_tags.update(tags)
            note.tags = list(existing_tags)

            mw.col.update_note(note)
            return True
        except Exception as e:
            print(f"Error adding tags: {e}")
            return False

    @staticmethod
    def get_deck_context(deck_name: str) -> dict[str, Any]:
        """Get comprehensive context about a deck for AI understanding."""
        if not mw.col:
            return {}

        try:
            cards = mw.col.find_cards(f'deck:"{deck_name}"')

            # Sample cards to understand structure
            sample_cards = []
            for card_id in cards[:10]:  # Sample first 10 cards
                card = mw.col.get_card(card_id)
                note = card.note()
                sample_cards.append(
                    {
                        "front": note.get("Front", "")[:100],  # First 100 chars
                        "back": note.get("Back", "")[:100],
                        "model": note.model()["name"],
                        "tags": note.tags,
                    }
                )

            return {
                "deck_name": deck_name,
                "total_cards": len(cards),
                "sample_cards": sample_cards,
                "model_names": list(
                    set(
                        mw.col.get_card(cid).note().model()["name"]
                        for cid in cards[:20]
                    )
                ),
            }
        except Exception as e:
            print(f"Error getting deck context: {e}")
            return {"deck_name": deck_name, "error": str(e)}

    @staticmethod
    def get_currently_reviewed_card() -> Optional[CardInfo]:
        """Get the card currently being reviewed (if in review mode)."""
        if not mw.col or not hasattr(mw, "reviewer"):
            return None

        try:
            if not mw.reviewer or not mw.reviewer.card:
                return None

            card = mw.reviewer.card
            note = card.note()

            return CardInfo(
                card_id=card.id,
                note_id=note.id,
                front=note.get("Front", ""),
                back=note.get("Back", ""),
                deck_name=AnkiService.deck_name_for_did(card.did),
                model_name=note.model()["name"],
                tags=note.tags,
            )
        except Exception as e:
            print(f"Error getting reviewed card: {e}")
            return None

    @staticmethod
    def get_current_context_card() -> Optional[CardInfo]:
        """Get the most relevant card based on current Anki context."""
        # Try: currently reviewed card > last added card > most recent card
        card = AnkiService.get_currently_reviewed_card()
        if card:
            return card

        return AnkiService.get_last_card()

    @staticmethod
    def search_cards_with_tags(tags: list[str], match_all: bool = False) -> list[int]:
        """Search for cards by tags.

        Args:
            tags: List of tags to search for
            match_all: If True, return cards with ALL tags. If False, return cards with ANY tag.
        """
        if not mw.col or not tags:
            return []

        try:
            if match_all:
                # Build query for all tags
                query = " ".join([f"tag:{tag}" for tag in tags])
            else:
                # Build query for any tag
                query = " or ".join([f"tag:{tag}" for tag in tags])

            return mw.col.find_cards(query)
        except Exception as e:
            print(f"Error searching cards by tags: {e}")
            return []

    @staticmethod
    def get_all_ai_generated_cards() -> list[CardInfo]:
        """Get all AI-generated cards (cards with ai_generated or related tags)."""
        if not mw.col:
            return []

        try:
            ai_tags = [
                "ai_generated",
                "ai_from_text",
                "ai_from_pdf",
                "ai_from_slide",
                "ai_from_screenshot",
            ]
            card_ids = AnkiService.search_cards_with_tags(ai_tags, match_all=False)

            cards = []
            for card_id in card_ids[:1000]:  # Limit to 1000 for performance
                card = AnkiService.get_card_by_id(card_id)
                if card:
                    cards.append(card)

            return cards
        except Exception as e:
            print(f"Error getting AI cards: {e}")
            return []

    @staticmethod
    def get_manual_cards(deck_name: Optional[str] = None) -> list[CardInfo]:
        """Get manually created cards (not AI-generated)."""
        if not mw.col:
            return []

        try:
            # Get all cards in deck (or collection)
            if deck_name:
                query = f'deck:"{deck_name}"'
                card_ids = mw.col.find_cards(query)
            else:
                # Avoid scanning the entire collection; sample recent cards only.
                card_ids = AnkiService.get_recent_cards(limit=2500)

            manual_cards = []
            from .tag_system import TagManager
            from pathlib import Path

            try:
                if getattr(mw, "col", None) and getattr(mw.col, "path", None):
                    base = Path(mw.col.path).parent / "ai_flashcards_tags"
                else:
                    base = Path.home() / ".ai_flashcards_tags"
            except Exception:
                base = Path.home() / ".ai_flashcards_tags"

            tag_manager = TagManager(base)

            for card_id in card_ids[:1000]:  # Limit to 1000 for performance
                card = AnkiService.get_card_by_id(card_id)
                if card and tag_manager.is_manual_card(card.tags):
                    manual_cards.append(card)

            return manual_cards
        except Exception as e:
            print(f"Error getting manual cards: {e}")
            return []
