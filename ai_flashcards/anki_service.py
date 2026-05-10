"""Service for interacting with Anki database and card management."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
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

    PICKER_CURRENT_DECK = "__AI_FLASHPICK_CURRENT_DECK__"

    @staticmethod
    def note_pair_preview(note: Any) -> tuple[str, str]:
        """First field + second field values for previews (works for every notetype)."""
        flds = list(getattr(note, "fields", None) or [])
        if len(flds) >= 2:
            return flds[0], flds[1]
        if len(flds) == 1:
            return flds[0], ""
        return "", ""

    @staticmethod
    def picker_tag_clause(tag: str) -> str:
        t = tag.replace('"', "")
        return f'tag:"{t}"'

    @staticmethod
    def picker_resolve_card_ids(
        deck_choice: str | None,
        *,
        tag: str | None = None,
        notetype_name: str | None = None,
        extra_search: str | None = None,
        limit: int = 400,
    ) -> list[int]:
        """Combine deck / tag / note-type filters with optional Browser-style search."""
        if not mw.col:
            return []

        tag_st = (tag or "").strip()
        nt_st = (notetype_name or "").strip()
        extra_st = (extra_search or "").strip()

        deck_is_current = deck_choice == AnkiService.PICKER_CURRENT_DECK
        deck_named = isinstance(deck_choice, str) and not deck_is_current

        deck_only_recent_sql = deck_named and not tag_st and not nt_st and not extra_st
        if deck_only_recent_sql:
            try:
                did = mw.col.decks.id_for_name(deck_choice)  # type: ignore[arg-type]
            except Exception:
                did = None
            if did is not None:
                try:
                    rows = mw.col.db.all(
                        "select id from cards where did = ? order by mod desc limit ?",
                        int(did),
                        limit,
                    )
                    return [int(r[0]) for r in rows]
                except Exception as e:
                    print(f"[AI Flashcards] deck SQL picker fallback failed: {e}")

        if deck_choice is None and not tag_st and not nt_st and not extra_st:
            return AnkiService.get_recent_cards(limit)

        parts: list[str] = []
        if deck_is_current:
            parts.append("deck:current")
        elif deck_named:
            parts.append(f'deck:"{deck_choice.replace(chr(34), "")}"')
        if tag_st:
            parts.append(AnkiService.picker_tag_clause(tag_st))
        if nt_st:
            parts.append(f'note:"{nt_st.replace(chr(34), "")}"')
        if extra_st:
            parts.append(extra_st)

        query = " ".join(parts).strip() if parts else "*"

        try:
            from anki.errors import InvalidInput, SearchError

            ids = mw.col.find_cards(query, order=True)
            return [int(x) for x in ids[:limit]]
        except (InvalidInput, SearchError, Exception) as e:
            print(f"[AI Flashcards] picker search failed ({query!r}): {e}")
            return []

    @staticmethod
    def picker_deck_combo_rows() -> list[tuple[str, str | None]]:
        """Human label (indented hierarchy) + userData deck path or sentinel."""
        if not mw.col:
            return []

        rows: list[tuple[str, str | None]] = [
            ("(All decks)", None),
            ("(Current deck)", AnkiService.PICKER_CURRENT_DECK),
        ]
        entries = sorted(
            mw.col.decks.all_names_and_ids(
                skip_empty_default=False, include_filtered=True
            ),
            key=lambda e: e.name.lower(),
        )
        for ent in entries:
            depth = max(0, len(ent.name.split("::")) - 1)
            indent = "\u2002" * min(depth * 3, 30)
            label = f"{indent}{ent.name}"
            rows.append((label, ent.name))
        return rows

    @staticmethod
    def picker_deck_full_names() -> list[str]:
        """Sorted full deck paths for building a hierarchy tree."""
        if not mw.col:
            return []
        return sorted(
            (
                e.name
                for e in mw.col.decks.all_names_and_ids(
                    skip_empty_default=False, include_filtered=True
                )
            ),
            key=str.lower,
        )

    @staticmethod
    def picker_notetype_combo_rows() -> list[tuple[str, str]]:
        """Display label + canonical name used in searches."""
        if not mw.col:
            return []

        pairs: list[tuple[str, str]] = []
        for nt in mw.col.models.all_names_and_ids():
            name = getattr(nt, "name", "") or ""
            pairs.append((name, name))
        pairs.sort(key=lambda x: x[0].lower())
        return pairs

    @staticmethod
    def picker_tag_combo_items() -> list[str]:
        if not mw.col:
            return []
        tags = mw.col.tags.all()
        tags.sort(key=str.lower)
        return tags[:500]

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
                front=(
                    note["Front"]
                    if "Front" in note
                    else AnkiService.note_pair_preview(note)[0]
                ),
                back=(
                    note["Back"]
                    if "Back" in note
                    else AnkiService.note_pair_preview(note)[1]
                ),
                deck_name=AnkiService.deck_name_for_did(card.did),
                model_name=note.note_type()["name"] if note.note_type() else "",
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

            front, back = AnkiService.note_pair_preview(note)
            return CardInfo(
                card_id=card_id,
                note_id=note.id,
                front=front,
                back=back,
                deck_name=AnkiService.deck_name_for_did(card.did),
                model_name=note.note_type()["name"] if note.note_type() else "",
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
                            nt_dict = card.note().note_type()
                            if nt_dict:
                                note_types_set.add(nt_dict["name"])
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
    def remove_tags_from_notes_for_cards(
        card_ids: Iterable[int],
        tags_to_remove: list[str],
    ) -> int:
        """Strip tags from every note reachable from the card ids.

        Notes shared by multiple selected cards are updated once.
        Returns how many notes were modified.
        """
        if not mw.col or not tags_to_remove:
            return 0
        rm = frozenset(tags_to_remove)
        nids: set[int] = set()
        for cid in card_ids:
            try:
                nids.add(int(mw.col.get_card(cid).nid))
            except Exception:
                continue
        changed = 0
        for nid in nids:
            try:
                note = mw.col.get_note(nid)
                new_tags = [t for t in note.tags if t not in rm]
                if len(new_tags) == len(note.tags):
                    continue
                note.tags = new_tags
                mw.col.update_note(note)
                changed += 1
            except Exception as e:
                print(f"[AI Flashcards] remove_tags note {nid}: {e}")
        return changed

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
                        "front": AnkiService.note_pair_preview(note)[0][:100],
                        "back": AnkiService.note_pair_preview(note)[1][:100],
                        "model": note.note_type()["name"] if note.note_type() else "",
                        "tags": note.tags,
                    }
                )

            model_names_seen: set[str] = set()
            for cid in cards[:20]:
                try:
                    nt = mw.col.get_card(cid).note().note_type()
                    if nt:
                        model_names_seen.add(nt["name"])
                except Exception:
                    continue

            return {
                "deck_name": deck_name,
                "total_cards": len(cards),
                "sample_cards": sample_cards,
                "model_names": sorted(model_names_seen),
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

            front, back = AnkiService.note_pair_preview(note)
            return CardInfo(
                card_id=card.id,
                note_id=note.id,
                front=front,
                back=back,
                deck_name=AnkiService.deck_name_for_did(card.did),
                model_name=note.note_type()["name"] if note.note_type() else "",
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
