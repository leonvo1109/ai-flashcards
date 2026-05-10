# AI Flashcards - Implementation Guide

## Overview

The AI Flashcards addon has been completely refactored from a proof-of-concept to a full-featured system for AI-assisted flashcard management and generation. The addon now provides three main workflows: card verification, multi-type card generation, and new card creation from various media types.

## Changes Made

### 1. Removed Proof-of-Concept Code

**Removed:**
- "Test prompting" dialog (simple text input/output for testing LLM connectivity)
- Associated UI state and event handlers

### 2. New Architecture

The addon now consists of three new service modules:

#### **anki_service.py** - Anki Database Integration
Provides low-level access to Anki data:
- `get_last_card()` - Retrieve the most recently added/viewed card
- `get_card_by_id(card_id)` - Get specific card info
- `search_cards(query)` - Search cards using Anki syntax
- `get_all_decks()` - List all decks with metadata
- `add_card()` - Add single card to collection
- `add_cards_batch()` - Bulk add cards
- `update_card()` - Modify existing card
- `add_tags_to_card()` - Add tags to existing card
- `get_deck_context()` - Get deck structure information (sample cards, models used, etc.)

#### **card_services.py** - AI Card Processing
Two main services:

**CardVerificationService:**
- `verify_card()` - AI checks for best practices (single info principle, clarity, etc.)
- Returns issues and suggested improvements
- Auto-generates replacement cards if single-info-principle violated

**CardGenerationService:**
- `generate_from_text()` - Create cards from plain text
- `generate_from_image_text()` - Create cards from OCR/extracted image text (PDFs, slides, screenshots)

#### **tag_system.py** - Tag Management
Intelligent tag system for card organization:
- `TagManager` - Manages predefined AI tags
- `DeckTagStrategy` - Generates deck-specific tags based on deck structure
- Built-in tags:
  - Verification: `ai_verified`, `ai_needs_review`
  - Source: `ai_from_text`, `ai_from_pdf`, `ai_from_slide`, `ai_from_screenshot`
  - Quality: `ai_single_info`, `ai_multi_type`, `ai_improvement`

#### **ui.py** - Completely Redesigned UI
New tabbed interface with three main workflows:

**Tab 1: Verify Card**
1. Automatically loads last added/viewed card
2. Allows card selection from dropdown
3. AI verification checks:
   - Single information principle (breaks complex cards into simpler ones)
   - Clarity and conciseness
   - Context appropriateness
4. Shows issues and generates replacement cards
5. User can accept suggested improvements by adding as new cards
6. Successfully verified cards marked with `ai_verified` tag

**Tab 2: Create Variants**
1. Select a card to enhance
2. Generate multiple card types from same information:
   - Definition cards
   - Reverse cards
   - Application cards
   - Example cards
3. Each variant tests the same knowledge from different angles
4. Preview and select which variants to add
5. Variants tagged with `ai_multi_type` + type name

**Tab 3: Create from Media**
1. Choose target deck
2. Select content source:
   - Text Input
   - PDF File
   - Screenshot/Image
   - Presentation Slide
3. Specify number of cards to generate (1-20)
4. Enter or select content
5. AI generates cards following single-information principle
6. Preview generated cards with selectable checkboxes
7. Add selected cards to chosen deck
8. Cards tagged with source type and `ai_needs_review`

### 3. Key Features

#### Single Information Principle Enforcement
- AI analyzes cards and identifies violations
- Automatically suggests splitting into multiple cards
- Each replacement card focuses on ONE concept

#### Deck-Context Awareness
- AI receives sample cards from deck
- Understands deck's note types and existing structure
- Generates cards that fit the deck's context and style

#### Intelligent Tag System
- Automatic tagging based on:
  - Generation source (text/PDF/image/slide)
  - Verification status
  - Card type/purpose
  - Deck structure
- Tags help organize and filter AI-generated cards

#### Async AI Processing
- All AI calls are properly async
- Non-blocking UI during processing
- Smooth user experience with status updates

#### Supported Providers
- Google Gemini (via google-genai library)
- Apple Intelligence (on compatible systems)
- Easily extensible for additional providers

### 4. File Structure

```
packages/ai_flashcards/
├── __init__.py              # Entry point (loads UI)
├── manifest.json            # Add-on metadata
├── config.json              # Default configuration
├── requirements-runtime.txt # Dependencies
├── ui.py                    # Main UI (refactored)
├── anki_service.py          # Anki database access [NEW]
├── card_services.py         # AI card processing [NEW]
├── tag_system.py            # Tag management [NEW]
├── use_cases.py             # Basic request wrapper (kept from proof-of-concept)
├── llm/
│   ├── base.py              # LLM provider interface
│   ├── types.py             # Type definitions
│   ├── factory.py           # Provider factory
│   └── providers/
│       ├── google_provider.py
│       └── apple_provider.py
└── lib/                     # Vendored dependencies
```

## Usage Workflow

### Verification Workflow
1. Open "AI Flashcards" → "Generate or Verify Cards"
2. Select "1. Verify Card" tab
3. Current card auto-loads (or select from dropdown)
4. Click "Verify with AI"
5. AI analyzes card and suggests improvements
6. Review issues and click "Add" on recommended replacements
7. Successfully verified cards marked as `ai_verified`

### Variant Generation Workflow
1. Open "AI Flashcards" → "Generate or Verify Cards"
2. Select "2. Create Variants" tab
3. Select card to enhance
4. Click "Generate Card Types"
5. AI creates 3-4 different card types testing same knowledge
6. Review variants and select which to add
7. Click OK to add all checked variants

### Media-Based Generation Workflow
1. Open "AI Flashcards" → "Generate or Verify Cards"
2. Select "3. Create from Media" tab
3. Choose target deck and content source
4. Enter or select content (text, PDF, screenshot, slide)
5. Specify number of cards (default: 5)
6. Click "Generate Cards"
7. Preview generated cards
8. Select which cards to add
9. Click OK to add to collection

## Configuration

Edit `config.json`:
```json
{
  "enabled": true,
  "provider": "google",  // or "apple"
  "model": "gemini-2-flash",
  "target_deck": "",  // Optional default
  "note_type": "",    // Optional default
  "max_cards_per_run": 10,
  "temperature": 0.2,
  "add_menu_entry": true,
  "gemini_api_key": ""  // For Google provider
}
```

## Design Decisions

### Why Async Pattern
- Non-blocking UI during AI processing
- Allows multiple requests in parallel
- Better user experience with status updates

### Why Tag System
- Automatic organization of AI-generated content
- Easy filtering and identification of AI-processed cards
- Deck-specific tagging for context awareness

### Why Single-Information-Principle Focus
- Proven best practice for spaced repetition
- Improves retention and recall
- Prevents cognitive overload

### Why Multiple Card Types
- Tests knowledge from different angles
- Supports various learning styles
- Deeper understanding through multiple exposures

## Future Enhancement Opportunities

1. **Media Extraction**
   - PDF text extraction (needs pypdf or similar)
   - Image OCR (needs pytesseract or similar)
   - Slide parsing (needs python-pptx or similar)

2. **Card Quality Scoring**
   - Rate cards on difficulty
   - Estimate review burden
   - Suggest optimizations

3. **Batch Processing**
   - Process multiple cards at once
   - Bulk verification across deck
   - Automated quality improvements

4. **More Providers**
   - OpenAI GPT-4
   - Anthropic Claude
   - Local LLMs

5. **Advanced Analytics**
   - Track which AI-generated cards have best retention
   - Learn from user behavior
   - Suggest improvements based on review data

6. **Integration with Anki Review**
   - AI suggestions during review
   - Rating effectiveness of variants
   - Dynamic difficulty adjustment

## Testing & Deployment

1. **Local Testing:**
   ```bash
   hatch run install-dev
   # Restart Anki
   ```

2. **Build Release:**
   ```bash
   hatch run build
   # Creates build/ai_flashcards.ankiaddon
   ```

3. **Deploy:**
   - Distribute .ankiaddon file
   - Users: Tools → Add-ons → Install from File

## Troubleshooting

### "No cards were generated"
- Check LLM provider credentials (Gemini API key)
- Verify content is not empty
- Try shorter content with fewer cards
- Check console for detailed error

### Cards not appearing
- Verify deck exists and is spelled correctly
- Check Anki file permissions
- Restart Anki after adding cards
- Check for duplicate card conflict

### UI Dialog Won't Open
- Check for Python syntax errors (run `python -m py_compile`)
- Verify Anki is up to date
- Check addon config is valid JSON
- Review Anki logs

## Credits & Version

- **Version:** 1.0.0 (Complete Refactor)
- **Date:** 2026-05-09
- **Previous:** Proof-of-Concept with simple test dialog
- **Now:** Full-featured AI flashcard system

