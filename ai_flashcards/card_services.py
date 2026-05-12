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


@dataclass
class AIPromptSettings:
    """User-configurable prompt and behavior controls."""

    agentic_enabled: bool = True
    strict_source_grounding: bool = True
    allow_model_knowledge_fallback: bool = False
    bullet_keywords_only: bool = True
    max_front_words: int = 14
    max_back_words: int = 10
    additional_instructions: str = ""
    generation_prompt_extra: str = ""
    variants_prompt_extra: str = ""
    verify_prompt_extra: str = ""
    temperature: float | None = None

    @classmethod
    def from_config(cls, config: dict | None) -> "AIPromptSettings":
        if config is None:
            # Keep backwards-compatible behavior for callers/tests that do not pass config.
            return cls(
                agentic_enabled=False,
                strict_source_grounding=False,
                allow_model_knowledge_fallback=True,
                bullet_keywords_only=True,
                max_front_words=14,
                max_back_words=10,
            )
        cfg = config or {}
        return cls(
            agentic_enabled=bool(cfg.get("ai_agentic_enabled", True)),
            strict_source_grounding=bool(cfg.get("ai_strict_source_grounding", True)),
            allow_model_knowledge_fallback=bool(
                cfg.get("ai_allow_model_knowledge_fallback", False)
            ),
            bullet_keywords_only=bool(cfg.get("ai_bullet_keywords_only", True)),
            max_front_words=max(4, int(cfg.get("ai_max_front_words", 14) or 14)),
            max_back_words=max(3, int(cfg.get("ai_max_back_words", 10) or 10)),
            additional_instructions=str(
                cfg.get("ai_additional_instructions", "") or ""
            ),
            generation_prompt_extra=str(
                cfg.get("ai_generation_prompt_extra", "") or ""
            ),
            variants_prompt_extra=str(cfg.get("ai_variants_prompt_extra", "") or ""),
            verify_prompt_extra=str(cfg.get("ai_verify_prompt_extra", "") or ""),
            temperature=float(cfg["temperature"]) if "temperature" in cfg else None,
        )


def _extract_json_fragment_from_llm_text(text: str) -> str:
    """Pull JSON from fenced blocks or trimmed raw JSON."""
    t = (text or "").strip().removeprefix("\ufeff")
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
    if not s:
        return None
    decoder = json.JSONDecoder()

    candidates = (s, _repair_common_json_issues(s))
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass

    for cand in candidates:
        if cand[0] not in "[{":
            continue
        try:
            obj, end = decoder.raw_decode(cand, 0)
            if cand[end:].strip() == "":
                return obj
        except json.JSONDecodeError:
            pass

    for cand in candidates:
        for i, ch in enumerate(cand):
            if ch not in "[{":
                continue
            try:
                obj, _end = decoder.raw_decode(cand, i)
            except json.JSONDecodeError:
                continue
            # Do not treat nested empty arrays (e.g. "tags": []) as the root value.
            if isinstance(obj, list) and len(obj) == 0 and i > 0:
                continue
            return obj

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


_CARD_LIST_KEYS = (
    "cards",
    "variants",
    "items",
    "results",
    "variants_generated",
    "flashcards",
    "generated_cards",
    "output",
)

_NESTED_CARD_PAYLOAD_KEYS = frozenset(
    {"card", "variant", "item", "flashcard", "payload", "content"}
)


def _flatten_card_payload(d: dict) -> dict:
    """Merge nested shapes like {\"type\": \"..\", \"card\": {\"front\": ...}}."""
    for key in _NESTED_CARD_PAYLOAD_KEYS:
        inner = d.get(key)
        if isinstance(inner, dict):
            return {**inner, **d}
    return d


def _coerce_card_object_list(parsed: object) -> list[dict]:
    """Accept a bare JSON array or a dict with common list keys."""
    if isinstance(parsed, list):
        raw = [x for x in parsed if isinstance(x, dict)]
        return [_flatten_card_payload(x) for x in raw]
    if isinstance(parsed, dict):
        for key in _CARD_LIST_KEYS:
            v = parsed.get(key)
            if isinstance(v, list):
                lst = [x for x in v if isinstance(x, dict)]
                if lst:
                    return [_flatten_card_payload(x) for x in lst]

        fallback = _dict_values_that_look_like_card_payloads(parsed)
        if fallback:
            return [_flatten_card_payload(x) for x in fallback]

    return []


_GENERATION_LIST_KEYS = ("cards", "items", "results", "flashcards", "generated_cards")


def _coerce_generation_card_list(parsed: object) -> list[dict]:
    """Normalize generate_from_text / image responses: array or {cards: [...]}."""
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        for key in _GENERATION_LIST_KEYS:
            v = parsed.get(key)
            if isinstance(v, list):
                lst = [x for x in v if isinstance(x, dict)]
                if lst:
                    return lst
    return []


def _coerce_single_info_card_list(parsed: object) -> list[dict]:
    """Normalize replacement-card arrays from the LLM."""
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        for key in _GENERATION_LIST_KEYS:
            v = parsed.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
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


def _normalize_compact_text(text: str, max_words: int) -> str:
    """Force concise output for flashcard fields."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    no_lines = re.sub(r"\s+", " ", raw)
    no_bullets = no_lines.lstrip("-*• ").strip()
    words = no_bullets.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]).rstrip(".,;:") + "..."
    return no_bullets


def _render_card_style_rules(settings: AIPromptSettings) -> str:
    """Renderable prompt fragment that enforces concise card text."""
    compact_rule = (
        "Use short keywords / compact bullet-like phrasing; avoid full sentences."
        if settings.bullet_keywords_only
        else "Prefer concise wording; avoid long explanations."
    )
    grounding_rule = (
        "Use ONLY provided source text and deck context/sample cards. "
        "Do not invent facts."
        if settings.strict_source_grounding
        else "Prefer provided source text and deck context/sample cards."
    )
    fallback_rule = (
        "If no usable facts are available, you may use minimal model knowledge "
        "and mark rationale accordingly."
        if settings.allow_model_knowledge_fallback
        else "If no usable facts are available, return empty cards instead of guessing."
    )
    return (
        f"{compact_rule}\n"
        f"{grounding_rule}\n"
        f"{fallback_rule}\n"
        f"Front max words: {settings.max_front_words}\n"
        f"Back max words: {settings.max_back_words}"
    )


class CardVerificationService:
    """Service for verifying cards and generating improvements."""

    def __init__(self, provider: LLMProvider, config: dict | None = None):
        self.provider = provider
        self.settings = AIPromptSettings.from_config(config)

    def _temperature(self, default: float) -> float:
        t = self.settings.temperature
        if t is None:
            return default
        return max(0.0, min(1.5, float(t)))

    async def verify_card(
        self,
        card_front: str,
        card_back: str,
        deck_context: dict,
    ) -> CardVerification:
        """Verify if a card follows best practices (single information principle, etc.)."""

        style_rules = _render_card_style_rules(self.settings)
        verify_extra = self.settings.verify_prompt_extra.strip()
        global_extra = self.settings.additional_instructions.strip()

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
        }""" + f"\n\nStyle and grounding constraints:\n{style_rules}"

        deck_context_str = json.dumps(deck_context, ensure_ascii=False)

        user_prompt = f"""Verify this flashcard:

Front: {card_front}
Back: {card_back}

Deck Context:
{deck_context_str}

Return JSON response."""
        if global_extra:
            user_prompt += f"\n\nGlobal extra instructions:\n{global_extra}"
        if verify_extra:
            user_prompt += f"\n\nVerify-specific extra instructions:\n{verify_extra}"

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._temperature(0.3),
                    max_tokens=1000,
                )
            )

            fragment = _extract_json_fragment_from_llm_text(
                response.text if response.text is not None else ""
            )
            parsed = _parse_json_embedded(fragment)
            if not isinstance(parsed, dict):
                raise ValueError("Verification response was not a JSON object")

            violations_raw = parsed.get("violations")
            violations: dict = (
                violations_raw if isinstance(violations_raw, dict) else {}
            )

            issues_raw = parsed.get("issues")
            issues: list[str] = (
                [str(x) for x in issues_raw] if isinstance(issues_raw, list) else []
            )

            is_valid = bool(parsed["is_valid"]) if "is_valid" in parsed else True

            # Build suggested improvements when the card fails validation or breaks
            # the single-information principle.
            suggested_improvements: list[dict] = []
            single_violation = bool(violations.get("single_info_principle", False))
            not_valid = not is_valid
            if single_violation or not_valid:
                build_cards = await self._build_single_info_cards(
                    card_front, card_back, deck_context
                )
                suggested_improvements.extend(build_cards)

            return CardVerification(
                is_valid=is_valid,
                issues=issues,
                suggested_improvements=suggested_improvements,
            )

        except Exception as e:
            print(f"Error verifying card: {e}")
            return CardVerification(
                is_valid=False,
                issues=[f"Verification error: {str(e)}"],
                suggested_improvements=[],
            )

    async def _build_single_info_cards(
        self, card_front: str, card_back: str, deck_context: dict
    ) -> list[dict]:
        """Build multiple cards that each focus on single information."""

        style_rules = _render_card_style_rules(self.settings)
        global_extra = self.settings.additional_instructions.strip()
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
        
        Return ONLY valid JSON, no markdown or additional text.""" + (
            f"\n\nStyle and grounding constraints:\n{style_rules}"
        )

        user_prompt = f"""Break this multi-concept card into single-information cards:

Front: {card_front}
Back: {card_back}

Context: {json.dumps(deck_context, ensure_ascii=False)}

Create 2-3 simpler cards that each focus on ONE concept."""
        if global_extra:
            user_prompt += f"\n\nGlobal extra instructions:\n{global_extra}"

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._temperature(0.5),
                    max_tokens=800,
                )
            )

            fragment = _extract_json_fragment_from_llm_text(
                response.text if response.text is not None else ""
            )
            parsed = _parse_json_embedded(fragment)
            cards = _coerce_single_info_card_list(parsed)
            if not cards:
                raise ValueError("No replacement cards in LLM response")
            compact_cards = [
                {
                    "type": "single_info_replacement",
                    "concept": card.get("concept"),
                    "front": _normalize_compact_text(
                        card.get("front", ""), self.settings.max_front_words
                    ),
                    "back": _normalize_compact_text(
                        card.get("back", ""), self.settings.max_back_words
                    ),
                }
                for card in cards
            ]
            return [c for c in compact_cards if c["front"] and c["back"]]
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

        style_rules = _render_card_style_rules(self.settings)
        variant_extra = self.settings.variants_prompt_extra.strip()
        global_extra = self.settings.additional_instructions.strip()
        system_prompt = (
            """You are an expert in creating diverse flashcard types to test knowledge from different angles.
        
        Generate 3-4 different card types (e.g., definition, reverse, application, example).
        Each variant must focus on ONE piece of knowledge (single-information principle).
        Think through these fixed internal steps before output:
        1) Identify explicit source facts from the card and deck context.
        2) Reject unsupported assumptions.
        3) Select 3-4 complementary testing angles.
        4) Produce concise cards using only supported facts.

        Respond with JSON only: either a JSON array, or an object { "cards": [ ... ] }.
        Each item:
        {
            "type": "short_type_name",
            "front": "question",
            "back": "answer",
            "rationale": "why this type helps"
        }"""
            + f"\n\nStyle and grounding constraints:\n{style_rules}"
        )

        deck_context_str = json.dumps(deck_context, ensure_ascii=False)
        user_prompt = f"""Generate diverse card types from this information:

Front: {card_front}
Back: {card_back}

Deck context:
{deck_context_str}

        Create 3–4 cards that test the same knowledge from different angles."""
        if global_extra:
            user_prompt += f"\n\nGlobal extra instructions:\n{global_extra}"
        if variant_extra:
            user_prompt += f"\n\nVariant-specific extra instructions:\n{variant_extra}"

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._temperature(0.55),
                    max_tokens=2048,
                )
            )

            fragment = _extract_json_fragment_from_llm_text(
                response.text if response.text is not None else ""
            )
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
                        "front": _normalize_compact_text(
                            front, self.settings.max_front_words
                        ),
                        "back": _normalize_compact_text(
                            back, self.settings.max_back_words
                        ),
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

    def __init__(self, provider: LLMProvider, config: dict | None = None):
        self.provider = provider
        self.settings = AIPromptSettings.from_config(config)

    def _temperature(self, default: float) -> float:
        t = self.settings.temperature
        if t is None:
            return default
        return max(0.0, min(1.5, float(t)))

    async def _extract_supported_facts(
        self, source_text: str, deck_context: dict, *, purpose: str
    ) -> list[str]:
        """Agentic step 1: extract concise facts strictly supported by source/context."""
        style_rules = _render_card_style_rules(self.settings)
        system_prompt = """You are a strict fact extractor for flashcard generation.
Return JSON only:
{
  "facts": ["fact 1", "fact 2"],
  "has_enough_information": true
}
Use only explicit evidence from source text and deck context samples.
Do not infer hidden facts."""
        user_prompt = (
            f"Purpose: {purpose}\n"
            f"Source text:\n{source_text}\n\n"
            f"Deck context:\n{json.dumps(deck_context, ensure_ascii=False)}\n\n"
            "Extract at most 18 concise facts."
        )
        if self.settings.additional_instructions.strip():
            user_prompt += (
                "\n\nGlobal extra instructions:\n"
                + self.settings.additional_instructions.strip()
            )
        response = await self.provider.complete(
            AgentRequest(
                system_prompt=system_prompt + f"\n\nConstraints:\n{style_rules}",
                user_prompt=user_prompt,
                temperature=self._temperature(0.15),
                max_tokens=1200,
            )
        )
        fragment = _extract_json_fragment_from_llm_text(response.text or "")
        parsed = _parse_json_embedded(fragment)
        if not isinstance(parsed, dict):
            return []
        facts_raw = parsed.get("facts")
        if not isinstance(facts_raw, list):
            return []
        facts = []
        for f in facts_raw:
            fx = _normalize_compact_text(str(f or ""), self.settings.max_back_words + 6)
            if fx:
                facts.append(fx)
        return facts[:18]

    async def generate_from_text(
        self, text: str, deck_context: dict, num_cards: int = 5
    ) -> list[dict[str, str]]:
        """Generate cards from plain text."""
        source_text = text

        style_rules = _render_card_style_rules(self.settings)
        facts: list[str] = []
        if self.settings.agentic_enabled:
            facts = await self._extract_supported_facts(
                source_text, deck_context, purpose="generate flashcards from text"
            )

        if (
            not facts
            and self.settings.strict_source_grounding
            and not self.settings.allow_model_knowledge_fallback
        ):
            return []

        source_basis = "\n".join(f"- {f}" for f in facts) if facts else source_text
        source_label = "extracted facts" if facts else "source text"

        system_prompt = (
            f"""You are an expert at creating high-quality flashcards from text.
        
Generate {num_cards} clear, concise flashcards following the SINGLE INFORMATION PRINCIPLE.
Each card should:
- Focus on ONE concept
- Have a clear, specific question on the front
- Have a concise, accurate answer on the back
- Be appropriate for the deck context
Think through these fixed internal steps:
1) select strongest supported facts
2) map one fact per card
3) compress wording to minimal useful terms
4) check every card is grounded in provided evidence

Respond with valid JSON array (no markdown):
[
    {{"front": "question", "back": "answer", "tags": ["tag1", "tag2"]}}
]""" + f"\n\nStyle and grounding constraints:\n{style_rules}"
        )

        deck_info = json.dumps(
            {
                "deck": deck_context.get("deck_name"),
                "existing_models": deck_context.get("model_names", []),
            }
        )

        user_prompt = f"""Create {num_cards} flashcards from this {source_label}:

{source_basis}

Deck context: {deck_info}

Return valid JSON array only."""
        if self.settings.additional_instructions.strip():
            user_prompt += (
                "\n\nGlobal extra instructions:\n"
                + self.settings.additional_instructions.strip()
            )
        if self.settings.generation_prompt_extra.strip():
            user_prompt += (
                "\n\nGeneration-specific extra instructions:\n"
                + self.settings.generation_prompt_extra.strip()
            )

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._temperature(0.45),
                    max_tokens=2000,
                )
            )

            resp_text = response.text
            fragment = _extract_json_fragment_from_llm_text(resp_text or "")
            parsed = _parse_json_embedded(fragment)
            cards = _coerce_generation_card_list(parsed)
            if not cards:
                raise ValueError("LLM returned no cards")

            out_cards = [
                {
                    "front": _normalize_compact_text(
                        card.get("front", ""), self.settings.max_front_words
                    ),
                    "back": _normalize_compact_text(
                        card.get("back", ""), self.settings.max_back_words
                    ),
                    "tags": (
                        card.get("tags", [])
                        if isinstance(card.get("tags"), list)
                        else []
                    ),
                }
                for card in cards
            ]
            return [c for c in out_cards if c["front"] and c["back"]]

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

        style_rules = _render_card_style_rules(self.settings)
        facts: list[str] = []
        if self.settings.agentic_enabled:
            facts = await self._extract_supported_facts(
                source_text,
                deck_context,
                purpose=f"generate flashcards from {image_type}",
            )
        if (
            not facts
            and self.settings.strict_source_grounding
            and not self.settings.allow_model_knowledge_fallback
        ):
            return []
        source_basis = "\n".join(f"- {f}" for f in facts) if facts else source_text

        system_prompt = (
            f"""You are an expert at extracting flashcard content from visual materials.

{type_instructions.get(image_type, "Extract the most important information.")}

Generate {num_cards} high-quality flashcards applying the SINGLE INFORMATION PRINCIPLE.
Each card focuses on ONE concept.
Think through these fixed internal steps:
1) list explicit evidence
2) keep only verifiable facts
3) generate concise one-fact cards
4) remove unsupported claims

Respond with valid JSON array (no markdown):
[
    {{"front": "question", "back": "answer", "tags": ["tag1"]}}
]""" + f"\n\nStyle and grounding constraints:\n{style_rules}"
        )

        user_prompt = f"""Create {num_cards} flashcards from this {image_type} content:

{source_basis}

Deck: {deck_context.get("deck_name", "Unknown")}

Return valid JSON array only."""
        if self.settings.additional_instructions.strip():
            user_prompt += (
                "\n\nGlobal extra instructions:\n"
                + self.settings.additional_instructions.strip()
            )
        if self.settings.generation_prompt_extra.strip():
            user_prompt += (
                "\n\nGeneration-specific extra instructions:\n"
                + self.settings.generation_prompt_extra.strip()
            )

        try:
            response = await self.provider.complete(
                AgentRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._temperature(0.45),
                    max_tokens=2000,
                )
            )

            resp_text = response.text
            fragment = _extract_json_fragment_from_llm_text(resp_text or "")
            parsed = _parse_json_embedded(fragment)
            cards = _coerce_generation_card_list(parsed)
            if not cards:
                raise ValueError("LLM returned no cards")
            out_cards = [
                {
                    "front": _normalize_compact_text(
                        card.get("front", ""), self.settings.max_front_words
                    ),
                    "back": _normalize_compact_text(
                        card.get("back", ""), self.settings.max_back_words
                    ),
                    "tags": (
                        card.get("tags", [])
                        if isinstance(card.get("tags"), list)
                        else []
                    ),
                }
                for card in cards
            ]
            return [c for c in out_cards if c["front"] and c["back"]]

        except Exception as e:
            print(f"Error generating cards from image: {e}")
            return await self.generate_from_text(
                source_text, deck_context, num_cards=num_cards
            )
