"""Service for verifying and enhancing flashcards using AI."""

import json
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
        return t.split("```json")[1].split("```")[0].strip()
    if "```" in t:
        return t.split("```")[1].split("```")[0].strip()
    return t


def _coerce_card_object_list(parsed: object) -> list[dict]:
    """Accept a bare JSON array or a dict with common list keys."""
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        for key in ("cards", "variants", "items"):
            v = parsed.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


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
                    temperature=0.7,
                    max_tokens=1600,
                )
            )

            fragment = _extract_json_fragment_from_llm_text(response.text)
            cards_data = _coerce_card_object_list(json.loads(fragment))

            cards: list[dict[str, str]] = []
            for card in cards_data:
                raw_front = card.get("front")
                raw_back = card.get("back")
                if not isinstance(raw_front, str) or not isinstance(raw_back, str):
                    continue
                front = raw_front.strip()
                back = raw_back.strip()
                if not front or not back:
                    continue
                rat = card.get("rationale")
                cards.append(
                    {
                        "type": (
                            card.get("type", "variant")
                            if isinstance(card.get("type"), str)
                            else "variant"
                        ),
                        "front": front,
                        "back": back,
                        "rationale": (
                            rat.strip() if isinstance(rat, str) and rat.strip() else ""
                        ),
                    }
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
