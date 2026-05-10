# AI Flashcards - Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     UI Layer (ui.py)                        │
│  - Main Dialog with 3 Tabs                                 │
│  - Dialog Managers & State                                 │
│  - Event Handlers                                          │
└────────┬────────────────────────┬──────────────┬──────────┘
         │                        │              │
    ┌────▼────┐        ┌──────────▼───────┐   ┌─▼──────────┐
    │ Anki    │        │ Card             │   │ Tag        │
    │ Service │        │ Services         │   │ Manager    │
    │         │        │                  │   │            │
    │ - Get   │        │ - Verify         │   │ - Manage   │
    │   Card  │        │ - Multi-Type     │   │   Tags     │
    │ - Add   │        │ - Generate       │   │ - Deck     │
    │   Card  │        │ - From Text      │   │   Specific │
    │ - Search│        │ - From Image     │   │   Tags     │
    │ - Deck  │        │                  │   │            │
    │   Info  │        │                  │   │            │
    └────┬────┘        └────────┬─────────┘   └──┬─────────┘
         │                      │                 │
         │              ┌───────▼──────────┐    │
         │              │   LLM Providers  │    │
         │              │                  │    │
         │              │ - Google Gemini  │    │
         │              │ - Apple Intell.  │    │
         │              │                  │    │
         └──────────────┤  (Async APIs)    │    │
                        └──────────────────┘    │
                                                │
                        ┌───────────────────────┘
                        │
                   ┌────▼──────┐
                   │   Anki    │
                   │ Collection│
                   │  (mw.col) │
                   └───────────┘
```

## Module Breakdown

### 1. UI Module (ui.py)

**Responsibilities:**
- Create and manage main dialog
- Handle user interactions
- Display information
- Manage async operations

**Key Classes:**
```python
UI:
  - show_main_dialog()          # Main entry point
  - _create_verify_tab()        # Verification interface
  - _create_multi_type_tab()    # Variants interface
  - _create_generate_tab()      # Media generation interface
  - _show_verification_results() # Display verification info
  - _show_improvements_dialog()  # Accept/reject improvements
  - _show_multi_type_results()   # Display variants
  - _show_generation_results()   # Show generated cards preview
```

**Flow:**
1. User opens menu → `show_main_dialog()`
2. Dialog displays with 3 tabs
3. User selects action & inputs data
4. Click button → Call async service
5. Show results → User confirms/rejects
6. Add to collection or modify existing

### 2. Anki Service (anki_service.py)

**Responsibilities:**
- Abstract Anki API for addon
- Provide high-level card operations
- Deck information retrieval
- Add/update cards

**Key Classes:**
```python
CardInfo:
  - card_id: int
  - note_id: int
  - front: str
  - back: str
  - deck_name: str
  - model_name: str
  - tags: list[str]

DeckInfo:
  - name: str
  - description: str
  - note_types: list[str]

AnkiService:
  - get_last_card() -> CardInfo           # Get most recent
  - get_card_by_id(card_id) -> CardInfo   # Get by ID
  - search_cards(query) -> list[int]      # Anki search
  - get_all_decks() -> list[DeckInfo]     # All deck info
  - add_card(front, back, deck) -> int    # Add one card
  - add_cards_batch() -> list[int]        # Bulk add
  - update_card() -> bool                 # Modify card
  - add_tags_to_card() -> bool            # Tag card
  - get_deck_context() -> dict            # Deck context
```

**Anki API Used:**
- `mw.col.get_card(card_id)` - Get card object
- `mw.col.find_cards(query)` - Search
- `mw.col.decks.*` - Deck operations
- `mw.col.models.*` - Note type operations
- `Card.note()` - Get note from card
- `mw.col.add_note()` - Add note to collection
- `mw.col.update_note()` - Update existing note

### 3. Card Services (card_services.py)

**Responsibilities:**
- AI-powered card analysis
- Card improvement suggestions
- Multi-type generation
- Single-info-principle checking

**Key Classes:**
```python
CardVerification:
  - is_valid: bool
  - issues: list[str]
  - suggested_improvements: list[dict]

MultiTypeCards:
  - cards: list[dict]           # Card variants
  - original_card_id: int

CardVerificationService:
  - verify_card()               # Check with AI
  - _build_single_info_cards()  # Generate replacements

CardGenerationService:
  - generate_from_text()        # Text → cards
  - generate_from_image_text()  # Image text → cards
```

**Prompts Used:**
1. **Verification Prompt:**
   - Checks: single info principle, clarity, cloze appropriateness, context fit
   - Returns: JSON with issues and violation flags

2. **Single-Info Splitting Prompt:**
   - Takes complex card
   - Generates 2-3 simpler cards
   - Each focuses on ONE concept

3. **Multi-Type Generation Prompt:**
   - From one card generates:
     - Definition type
     - Reverse type
     - Application type
     - Example type

4. **Text to Cards Prompt:**
   - Takes text input
   - Generates 5-20 focused Q&A pairs
   - Applies single-info principle

5. **Image to Cards Prompt:**
   - Takes OCR/extracted text
   - Context: slide/screenshot/PDF different prompts
   - Generates focused cards

### 4. Tag System (tag_system.py)

**Responsibilities:**
- Define and manage tags
- Generate appropriate tags for cards
- Deck-specific tagging strategy

**Key Classes:**
```python
TagConfig:
  - default_tags: dict          # Tag descriptions
  - verification_tags: list     # Verified/needs review
  - generation_source_tags: list # Source types

TagManager:
  - _load_config() -> TagConfig
  - _save_config()
  - get_verification_tags()     # For verified/unverified
  - get_source_tag()            # By source type
  - get_generation_tags()       # Complete set
  - get_tag_description()       # Human readable
  - add_custom_tag()
  - get_all_ai_tags()

DeckTagStrategy:
  - get_deck_specific_tags()    # Parse deck name
  - get_recommended_tags_for_card() # Content-based tags
```

**Tag Categories:**

1. **Verification (1 tag per card):**
   - `ai_verified` - Passes all checks
   - `ai_needs_review` - Needs human review

2. **Generation Source (1 tag per card):**
   - `ai_from_text` - Plain text
   - `ai_from_pdf` - PDF document
   - `ai_from_slide` - Presentation
   - `ai_from_screenshot` - Image/screenshot

3. **Quality Indicators (0-2 tags):**
   - `ai_single_info` - Follows principle
   - `ai_multi_type` - Part of variant set
   - `ai_improvement` - Suggested replacement

4. **Difficulty (1 tag per card):**
   - `difficulty_easy` - Simple (< 10 words)
   - `difficulty_medium` - Standard (10-30 words)
   - `difficulty_hard` - Complex (> 30 words)

## Data Flow Examples

### Verification Flow

```
User clicks "Verify with AI"
  ↓
UI gets selected card via AnkiService.get_card_by_id()
  ↓
UI gets deck context via AnkiService.get_deck_context()
  ↓
UI calls CardVerificationService.verify_card()
  ↓
Service creates prompt with card + deck context
  ↓
Sends to LLM provider (Google/Apple) [ASYNC]
  ↓
LLM analyzes and returns issues + violations
  ↓
Service checks if single-info violated
  ↓
If violated: calls _build_single_info_cards()
  → LLM generates replacement cards
  ↓
Returns CardVerification object
  ↓
UI displays results + suggested improvements
  ↓
User clicks "Add" to accept improvements
  ↓
For each improvement:
  - AnkiService.add_card() creates new card
  - Tags with ai_improvement + ai_needs_review
  ↓
If verified successfully:
  - AnkiService.add_tags_to_card(card_id, ["ai_verified"])
```

### Generation Flow

```
User enters content + selects deck
  ↓
User clicks "Generate Cards"
  ↓
UI validates input
  ↓
Gets deck context via AnkiService.get_deck_context()
  ↓
Determines if text/image source
  ↓
Calls appropriate CardGenerationService method
  ↓
Service creates appropriate prompt
  ↓
Sends to LLM provider [ASYNC]
  ↓
LLM generates JSON array of cards
  ↓
Service parses JSON response
  ↓
Returns list of card dicts
  ↓
UI displays preview with checkboxes
  ↓
User selects cards to add
  ↓
For each selected card:
  - AnkiService.add_card()
  - Adds source tag via TagManager
  - Adds ai_needs_review tag
  ↓
Shows "X cards added" confirmation
```

## Error Handling

**Structured Exception Handling:**

1. **Anki Service:**
   - Returns `None` if operation fails
   - Prints error message
   - Allows UI to handle gracefully

2. **Card Services:**
   - Catches JSON parse errors (malformed AI response)
   - Falls back to empty results
   - Logs error to console

3. **UI:**
   - Wraps async operations in try/except
   - Shows user warning with error message
   - Re-enables buttons on error
   - Logs full traceback

## Async Pattern

**Why async?**
- LLM calls are network I/O bound
- Prevents UI freezing
- Allows status updates

**Implementation:**
```python
async def verify_card():
    # UI update
    button.setText("Verifying...")
    button.setEnabled(False)
    
    try:
        # Async operation - doesn't block UI
        result = await service.verify_card(...)
        
        # Back on main thread
        button.setText("Verify with AI")
        button.setEnabled(True)
        show_results(result)
        
    except Exception as e:
        button.setEnabled(True)
        show_warning(str(e))

# Called with:
verify_button.clicked.connect(
    lambda: asyncio.run(verify_card())
)
```

## Provider Interface

**Protocol (base.py):**
```python
class LLMProvider(Protocol):
    async def complete(
        self, 
        req: AgentRequest
    ) -> AgentResponse: ...
```

**Request:**
```python
AgentRequest:
  - system_prompt: str
  - user_prompt: str
  - tools: list[ToolSpec]        # Optional
  - temperature: float
  - max_tokens: int
```

**Response:**
```python
AgentResponse:
  - text: str                     # Main response
  - tool_calls: list[ToolCall]    # Optional
  - raw: Any                      # Raw provider response
```

**Adding New Provider:**
1. Create `new_provider.py` in `llm/providers/`
2. Implement async `complete()` method
3. Add to factory.py
4. Add config option to config.json

## Testing Checklist

- [ ] Build succeeds: `python scripts/build_all.py`
- [ ] Addon installs: `hatch run install-dev`
- [ ] Menu appears in Anki
- [ ] Dialog opens
- [ ] Card loads automatically
- [ ] Can select different card
- [ ] Verification works (requires API key)
- [ ] Results display correctly
- [ ] Cards can be added to collection
- [ ] Tags appear on new cards
- [ ] Variants generate as expected
- [ ] Media generation works
- [ ] Multiple cards can be selected/added
- [ ] Error states handled gracefully

## Performance Considerations

1. **Anki Operations:**
   - `get_deck_context()` samples only 10-20 cards for speed
   - `search_cards()` for large decks is fast (native Anki)

2. **AI Calls:**
   - All async to prevent UI blocking
   - 30-60 second timeout expected (network-dependent)
   - JSON parsing optimized for large responses

3. **Memory:**
   - Dialog state stored in UI object
   - Single dialog instance per session
   - Minimal memory overhead

4. **Tag Operations:**
   - Tag config cached in TagManager
   - Minimal I/O for config persistence

## Future Extensibility

**Adding Features:**

1. **New Card Type:**
   - Add to CardGenerationService
   - Create appropriate prompt
   - Update UI tab if needed

2. **New Tag Category:**
   - Add to TagConfig defaults
   - Update DeckTagStrategy if rule-based
   - Update UI tag display

3. **New Provider:**
   - Implement LLMProvider protocol
   - Add to factory.py
   - Add config options
   - Update documentation

4. **Media Support:**
   - Implement extraction in card_services.py
   - Add to UI media selector
   - Create appropriate prompt
   - Test with samples

## Debugging Tips

1. **Print Statements:**
   ```python
   print(f"Debug: {variable}")  # Console output
   ```

2. **Check Config:**
   ```python
   config = mw.addonManager.getConfig("ai_flashcards")
   print(config)
   ```

3. **Test Prompts:**
   - Use Google AI Studio to test prompts
   - Verify JSON response format
   - Test with real Anki card data

4. **Inspect Cards:**
   - Use Anki's Browser to view generated cards
   - Check tags are applied correctly
   - Verify deck placement

5. **Monitor Logs:**
   - Anki console (View → Debugging → Error Console)
   - Exception tracebacks show exact locations
   - Check for provider-specific errors

