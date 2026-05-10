# AI Flashcards (Anki add-on)

AI-assisted **verification**, **variant** cards, and **generation** from text/media. Uses your collection’s notes (defaults to **Basic** with `Front` / `Back`).

## In Anki

**Tools → AI Flashcards** — open the main dialog (verify, variants, create from media).  
Tag/hierarchy metadata is stored beside the profile in `ai_flashcards_tags/` (see `tag_system.py` / `card_hierarchy.py`).

## Configuration

**Tools → Add-ons → AI Flashcards → Config**

| Field | Meaning |
|-------|--------|
| `provider` | `"google"` (Gemini) or `"apple"` (macOS on-device, where available) |
| `gemini_api_key` | Google AI API key; optional if `GOOGLE_API_KEY` is set in the environment |
| `model` | Gemini model id (provider-specific default if empty) |
| `target_deck` | Deck for new notes |
| `note_type` | Note type name (often `Basic`) |
| `temperature` | LLM sampling temperature |

Example (Google):

```json
{
  "enabled": true,
  "provider": "google",
  "model": "gemini-2.0-flash",
  "gemini_api_key": "",
  "target_deck": "Default",
  "note_type": "Basic",
  "max_cards_per_run": 10,
  "temperature": 0.2
}
```

Example (Apple): set `"provider": "apple"`; key not required.

## Source map

| Module | Role |
|--------|------|
| `__init__.py` | Entry point, hooks, bundled `lib/` path |
| `ui_enhanced.py` | Menus and PyQt dialogs |
| `anki_service.py` | `mw.col` access helpers |
| `card_services.py` | Verify / generate LLM flows |
| `tag_system.py` / `card_hierarchy.py` | JSON sidecar data |
| `llm/` | Provider factory and implementations |

## Build from monorepo root

```bash
uv run hatch run install-dev
```

Output add-on zip: run `python scripts/build_all.py` → `build/ai_flashcards.ankiaddon`.
