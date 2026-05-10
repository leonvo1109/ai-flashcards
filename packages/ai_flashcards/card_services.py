"""Service for verifying and enhancing flashcards using AI."""

import json
import re
from dataclasses import dataclass

from .llm.base import LLMProvider
from .llm.types import AgentRequest


@dataclass
class CardVerification:
    """Result of card verification."""

    is_valid: bool
    issues: list[str]
    suggested_improvements: list[dict]  # List of replacement or related cards


@dataclass
class MultiTypeCards:
    """Multiple cards generated from single information."""

    cards: list[dict[str, str]]  # Each dict has 'type', 'front', 'back'
    original_card_id: int


def _extract_json_fragment_from_llm_text(text: str) -> str:
    """Pull JSON from fenced blocks or trimmed raw JSON."""
    t = text.strip()
    if "```json" in t:
        inner = t.split("```json", 1)[1]
        inner = inner.split("```", 1)[0] if "```" in inner else inner
        return inner.strip()
    if "```" in t:
        inner = t.split("```", 1)[1]
        inner = inner.split("```", 1)[0] if "```" in inner else inner
        return inner.strip()
    return t


def _repair_common_json_issues(s: str) -> str:
    """Strip trailing commas that some models emit before ] or }."""
    s = re.sub(r",\s*]", "]", s)
    s = re.sub(r",\s*}", "}", s)
    return s


def _parse_json_embedded(fragment: str) -> object | None:
    """Parse JSON possibly preceded/followed by prose; tolerate minor damage."""
    s = fragment.strip()
    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch in "[{":
            try:
                obj, _ = decoder.raw_decode(s, i)
                return obj
            except json.JSONDecodeError:
                continue

    repaired = _repair_common_json_issues(s)
    for i, ch in enumerate(repaired):
        if ch in "[{":
            try:
                obj, _ = decoder.raw_decode(repaired, i)
                return obj
            except json.JSONDecodeError:
                continue

    try:
        return json.loads(_repair_common_json_issues(s))
    except json.JSONDecodeError:
        pass
    return None


def _dict_values_that_look_like_card_payloads(parsed: dict) -> list[dict]:
    """Handle { \"card_a\": {\"front\": ...}, ... } without a top-level cards array."""

    alias_pairs = (
        ("front", "back"),
        ("question", "answer"),
        ("prompt", "response"),
        ("q", "a"),
        ("stem", "answer"),
    )

    candidates: list[dict] = []
    for key, val in parsed.items():
        if key in frozenset(
            {"cards", "variants", "items", "results", "metadata", "summary", "note"}
        ):
            continue
        if not isinstance(val, dict):
            continue
        keys_lower = {str(k).lower() for k in val}
        matched = False
        for fk, bk in alias_pairs:
            if fk in keys_lower and bk in keys_lower:
                matched = True
                break
        if matched:
            candidates.append(val)
    return candidates


def _coerce_card_object_list(parsed: object) -> list[dict]:
    """Accept a bare JSON array or a dict with common list keys."""
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        for key in ("cards", "variants", "items", "results", "variants_generated"):
            v = parsed.get(key)
            if isinstance(v, list):
                lst = [x for x in v if isinstance(x, dict)]
                if lst:
                    return lst

        fallback = _dict_values_that_look_like_card_payloads(parsed)
        if fallback:
            return fallback

    return []


def _text_field_from_card_dict(card: dict, *keys: str) -> str:
    """Read first matching key case-insensitively; coerce scalars to str."""
    lower_map = {str(k).lower(): v for k, v in card.items()}
    for k in keys:
        v = lower_map.get(k.lower())
        if v is None:
            continue
        if isinstance(v, bool):
            s = "true" if v else "false"
        elif isinstance(v, str):
            s = v.strip()
        else:
            s = str(v).strip()
        if s:
            return s
    return ""


class CardVerificationService:
    """Service for verifying cards and generating improvements."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def verify_card(
        self,
        card_front: str,
        card_back: str,
        deck_context: dict,
    ) -> CardVerification:
        """Verify if a card follows best practices (single information principle, etc.)."""

        system_prompt = """You are an expert in spaced repetition and flashcard design. 
        Your task is to verify if a flashcard follows best practices:
        
        1. Single information principle: Each card should focus on ONE concept
        2. Clarity: The front and back should be clear and concise
        3. Cloze appropriateness: Consider if cloze deletion would be better
        4. Context appropriateness: Card should fit the deck's context
        
        Respond with a JSON object containing:
        {
            "is_valid": boolean,
            "issues": [list of identified issues],
            "violations": {
                "single_info_principle": boolean,
                "clarity": boolean,
                "other": list of other issues
            },
            "suggestions": [list of specific improvements],
            "recommended_card_types": [list of alternative card types that might work]
        }"""

        deck_context_str = json.dumps(deck_context, ensure_ascii=False)

        user_prompt = f"""Verify this flashcard:

Front: {card_front}
Back: {card_back}

Deck Context:
{deck_context_str}

Return JSON response."""

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.3,
                    max_tokens=1000,
                )
            )

            # Parse the JSON response
            result = json.loads(response.text)

            # Build suggested improvements when the card fails validation or breaks
            # the single-information principle.
            suggested_improvements: list[dict] = []
            single_violation = result.get("violations", {}).get(
                "single_info_principle", False
            )
            not_valid = not result.get("is_valid", True)
            if single_violation or not_valid:
                build_cards = await self._build_single_info_cards(
                    card_front, card_back, deck_context
                )
                suggested_improvements.extend(build_cards)

            return CardVerification(
                is_valid=result.get("is_valid", True),
                issues=result.get("issues", []),
                suggested_improvements=suggested_improvements,
            )

        except Exception as e:
            print(f"Error verifying card: {e}")
            return CardVerification(
                is_valid=True,
                issues=[f"Verification error: {str(e)}"],
                suggested_improvements=[],
            )

    async def _build_single_info_cards(
        self, card_front: str, card_back: str, deck_context: dict
    ) -> list[dict]:
        """Build multiple cards that each focus on single information."""

        system_prompt = """You are an expert at applying the single information principle.
        Breaking down complex cards into simpler, single-concept cards.
        
        Respond with a JSON array of card objects:
        [
            {
                "front": "focused question",
                "back": "concise answer",
                "concept": "main concept covered"
            }
        ]
        
        Return ONLY valid JSON, no markdown or additional text."""

        user_prompt = f"""Break this multi-concept card into single-information cards:

Front: {card_front}
Back: {card_back}

Context: {json.dumps(deck_context, ensure_ascii=False)}

Create 2-3 simpler cards that each focus on ONE concept."""

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.5,
                    max_tokens=800,
                )
            )

            # Extract JSON from response (might have markdown formatting)
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            cards = json.loads(text.strip())
            return [
                {
                    "type": "single_info_replacement",
                    "concept": card.get("concept"),
                    "front": card.get("front"),
                    "back": card.get("back"),
                }
                for card in cards
            ]
        except Exception as e:
            print(f"Error building single info cards: {e}")
            return []

    async def generate_multi_type_cards(
        self,
        card_front: str,
        card_back: str,
        deck_context: dict,
        *,
        original_card_id: int = 0,
    ) -> MultiTypeCards:
        """Generate multiple different types of cards from the same information."""

        system_prompt = """You are an expert in creating diverse flashcard types to test knowledge from different angles.
        
        Generate 3-4 different card types (e.g., definition, reverse, application, example).
        Each variant must focus on ONE piece of knowledge (single-information principle).

        Respond with JSON only: either a JSON array, or an object { "cards": [ ... ] }.
        Each item:
        {
            "type": "short_type_name",
            "front": "question",
            "back": "answer",
            "rationale": "why this type helps"
        }"""

        deck_context_str = json.dumps(deck_context, ensure_ascii=False)
        user_prompt = f"""Generate diverse card types from this information:

Front: {card_front}
Back: {card_back}

Deck context:
{deck_context_str}

        Create 3–4 cards that test the same knowledge from different angles."""

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.55,
                    max_tokens=2048,
                )
            )

            fragment = _extract_json_fragment_from_llm_text(response.text)
            parsed = _parse_json_embedded(fragment)
            if parsed is None:
                head = fragment[:480].replace("\n", " ")
                tail = fragment[-320:].replace("\n", " ") if len(fragment) > 480 else ""
                print(
                    "generate_multi_type_cards: JSON parse failed. "
                    f"Head: {head!r}{' … ' + repr(tail) if tail else ''}"
                )
                return MultiTypeCards(cards=[], original_card_id=original_card_id)

            cards_data = _coerce_card_object_list(parsed)

            cards: list[dict[str, str]] = []
            for card in cards_data:
                front = _text_field_from_card_dict(
                    card, "front", "question", "prompt", "q", "stem"
                )
                back = _text_field_from_card_dict(
                    card, "back", "answer", "response", "a", "explanation"
                )
                if not front or not back:
                    continue

                type_raw = (
                    card.get("type")
                    or card.get("card_type")
                    or card.get("variant_type")
                )
                if isinstance(type_raw, str) and type_raw.strip():
                    vtype = type_raw.strip()
                else:
                    vtype = "variant"

                rat = (
                    _text_field_from_card_dict(
                        card, "rationale", "why", "reason", "explanation_notes"
                    )
                    or ""
                )
                cards.append(
                    {
                        "type": vtype,
                        "front": front,
                        "back": back,
                        "rationale": rat,
                    }
                )

            if cards_data and not cards:
                print(
                    "generate_multi_type_cards: parsed "
                    f"{len(cards_data)} object(s) but none had usable front/back text."
                )

            return MultiTypeCards(cards=cards, original_card_id=original_card_id)

        except Exception as e:
            print(f"Error generating multi-type cards: {e}")
            return MultiTypeCards(cards=[], original_card_id=original_card_id)


class CardGenerationService:
    """Service for generating cards from various media types."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_from_text(
        self, text: str, deck_context: dict, num_cards: int = 5
    ) -> list[dict[str, str]]:
        """Generate cards from plain text."""
        source_text = text

        system_prompt = f"""You are an expert at creating high-quality flashcards from text.
        
Generate {num_cards} clear, concise flashcards following the SINGLE INFORMATION PRINCIPLE.
Each card should:
- Focus on ONE concept
- Have a clear, specific question on the front
- Have a concise, accurate answer on the back
- Be appropriate for the deck context

Respond with valid JSON array (no markdown):
[
    {{"front": "question", "back": "answer", "tags": ["tag1", "tag2"]}}
]"""

        deck_info = json.dumps(
            {
                "deck": deck_context.get("deck_name"),
                "existing_models": deck_context.get("model_names", []),
            }
        )

        user_prompt = f"""Create {num_cards} flashcards from this text:

{source_text}

Deck context: {deck_info}

Return valid JSON array only."""

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.6,
                    max_tokens=2000,
                )
            )

            # Parse JSON response
            resp_text = response.text
            if "```json" in resp_text:
                resp_text = resp_text.split("```json")[1].split("```")[0]
            elif "```" in resp_text:
                resp_text = resp_text.split("```")[1].split("```")[0]

            cards = json.loads(resp_text.strip())
            if not isinstance(cards, list) or not cards:
                raise ValueError("LLM returned no cards")

            return [
                {
                    "front": card.get("front", ""),
                    "back": card.get("back", ""),
                    "tags": card.get("tags", []),
                }
                for card in cards
            ]

        except Exception as e:
            print(f"Error generating cards from text: {e}")
            # Fallback: create simple Q/A pairs by splitting text into sentences
            try:
                import re

                sentences = [
                    s.strip()
                    for s in re.split(r"(?<=[.!?])\s+", source_text)
                    if s.strip()
                ]
                cards_out = []
                for i, sent in enumerate(sentences[:num_cards]):
                    # Build a naive front/back: question asks to summarize/explain sentence
                    front = f"Explain: {sent[:80]}..."
                    back = sent
                    cards_out.append({"front": front, "back": back, "tags": []})
                if cards_out:
                    return cards_out

                # Final fallback: one card from the full text
                snippet = source_text.strip().replace("\n", " ")[:180]
                if snippet:
                    return [
                        {
                            "front": f"Summarize: {snippet[:80]}...",
                            "back": snippet,
                            "tags": ["ai_fallback"],
                        }
                    ]

                return []
            except Exception:
                return []

    async def generate_from_image_text(
        self, image_text: str, image_type: str, deck_context: dict, num_cards: int = 5
    ) -> list[dict[str, str]]:
        """Generate cards from image text (screenshots, slides, PDFs, etc.)."""
        source_text = image_text

        type_instructions = {
            "slide": "This is from presentation slides. Focus on key concepts and definitions.",
            "screenshot": "This is from a screenshot. Extract and clarify the practical information.",
            "pdf": "This is from a PDF document. Focus on important concepts and key takeaways.",
        }

        system_prompt = f"""You are an expert at extracting flashcard content from visual materials.

{type_instructions.get(image_type, "Extract the most important information.")}

Generate {num_cards} high-quality flashcards applying the SINGLE INFORMATION PRINCIPLE.
Each card focuses on ONE concept.

Respond with valid JSON array (no markdown):
[
    {{"front": "question", "back": "answer", "tags": ["tag1"]}}
]"""

        user_prompt = f"""Create {num_cards} flashcards from this {image_type} content:

{source_text}

Deck: {deck_context.get("deck_name", "Unknown")}

Return valid JSON array only."""

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.6,
                    max_tokens=2000,
                )
            )

            # Parse JSON response
            resp_text = response.text
            if "```json" in resp_text:
                resp_text = resp_text.split("```json")[1].split("```")[0]
            elif "```" in resp_text:
                resp_text = resp_text.split("```")[1].split("```")[0]

            cards = json.loads(resp_text.strip())
            if not isinstance(cards, list) or not cards:
                raise ValueError("LLM returned no cards")
            return [
                {
                    "front": card.get("front", ""),
                    "back": card.get("back", ""),
                    "tags": card.get("tags", []),
                }
                for card in cards
            ]

        except Exception as e:
            print(f"Error generating cards from image: {e}")
            return await self.generate_from_text(
                source_text, deck_context, num_cards=num_cards
            )
