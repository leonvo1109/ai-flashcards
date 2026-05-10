# AI Flashcards - User Guide

## Getting Started

### Installation

1. Download the latest `ai_flashcards.ankiaddon` file
2. Open Anki
3. Go to **Tools** → **Add-ons** → **Install from File**
4. Select the addon file
5. Restart Anki

### Initial Configuration

1. Open **Tools** → **Add-ons**
2. Find "AI Flashcards" in the list
3. Click **Config** (or the gear icon)
4. Configure your AI provider:

**For Google Gemini:**
```json
{
  "enabled": true,
  "provider": "google",
  "model": "gemini-2-flash",
  "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
  "temperature": 0.2
}
```

**For Apple Intelligence:**
```json
{
  "enabled": true,
  "provider": "apple",
  "temperature": 0.2
}
```

### Getting an API Key (Gemini)

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikeys)
2. Click "Create API Key"
3. Copy the key
4. Paste into addon config
5. Save

## Main Features

### Feature 1: Verify Your Cards

✓ **What it does:** Checks if your flashcards follow best practices

1. Click **Tools** → **AI Flashcards** → **Generate or Verify Cards**
2. Go to **1. Verify Card** tab
3. Your last card automatically loads
4. Click **Verify with AI**
5. AI analyzes your card for:
   - ✓ Single information principle (one concept per card)
   - ✓ Clarity and conciseness
   - ✓ Appropriate for your deck

**What happens next:**
- **Card is good:** Marked as "ai_verified" ✓
- **Issues found:** AI suggests splitting into multiple cards
  - Click **Add** to accept replacement cards
  - Cards are added with "ai_needs_review" tag

**Example:**
```
BAD Card (too much info):
Front: What are the three main components of the digestive system and their functions?
Back: Mouth (breaks down food), stomach (churns and mixes), intestines (absorbs nutrients)

GOOD Cards (after AI verification):
Front: What is the primary function of the mouth in digestion?
Back: To break down food mechanically and chemically with saliva

Front: What is the stomach's role in the digestive process?
Back: To churn and mix food with gastric juices into a paste called chyme

Front: What does the small intestine do in digestion?
Back: Absorbs nutrients from digested food into the bloodstream
```

### Feature 2: Create Card Variants

✓ **What it does:** Generates multiple card types testing the same knowledge from different angles

1. Click **Tools** → **AI Flashcards** → **Generate or Verify Cards**
2. Go to **2. Create Variants** tab
3. Select the card you want to enhance
4. Click **Generate Card Types**
5. AI creates 3-4 different card formats:
   - Definition (question-answer)
   - Reverse (answer as question)
   - Application (practical use case)
   - Example (illustrative example)

**Why this helps:**
- Tests your knowledge multiple ways
- Leads to deeper understanding
- Better long-term retention

**Example for "Python":
```
Original: What is Python?
         A programming language

Variant 1 (Definition):
Front: Define Python
Back: A high-level, interpreted programming language for general-purpose programming

Variant 2 (Reverse):
Front: Which popular language is known for syntax simplicity and readability?
Back: Python

Variant 3 (Application):
Front: When would you use Python instead of C++?
Back: When you prioritize development speed and readability over raw performance

Variant 4 (Example):
Front: Give an example of a use case for Python
Back: Web development (Django, Flask), data analysis (Pandas), machine learning (TensorFlow)
```

### Feature 3: Create Cards from Media

✓ **What it does:** Generate cards from text, PDFs, images, or slides

1. Click **Tools** → **AI Flashcards** → **Generate or Verify Cards**
2. Go to **3. Create from Media** tab
3. Choose target deck
4. Choose content source:
   - **Text Input:** Paste text directly
   - **PDF File:** Select a PDF file
   - **Screenshot/Image:** Select an image with text
   - **Presentation Slide:** Select slide content
5. Set number of cards (1-20, default 5)
6. Click **Generate Cards**
7. Preview generated cards
8. Check boxes for cards you want to add
9. Click **OK** to add to deck

**AI automatically:**
- Follows single-information principle
- Creates clear, concise Q&A pairs
- Tags cards appropriately
- Fits cards to your deck's style

**Supported Formats:**
- Text (.txt, copy-paste)
- Images (.png, .jpg, .jpeg)
- PDFs (.pdf)
- Slide content (text extracted from .pptx)

## Card Tags Explained

Tags help organize AI-generated cards:

### Verification Status
- `ai_verified` - Card passes all checks ✓
- `ai_needs_review` - Human review recommended ⚠

### Generation Source
- `ai_from_text` - Generated from text input
- `ai_from_pdf` - Generated from PDF
- `ai_from_image` - Generated from screenshot/image
- `ai_from_slide` - Generated from presentation slide

### Quality Indicators
- `ai_single_info` - Follows single information principle
- `ai_multi_type` - Part of variant set
- `ai_improvement` - Suggested replacement for existing card

### Difficulty
- `difficulty_easy` - Simple answer (< 10 words)
- `difficulty_medium` - Standard answer (10-30 words)
- `difficulty_hard` - Complex answer (> 30 words)

## Tips for Best Results

### Content Generation Tips

1. **Be Specific in Your Input**
   - Good: "The process of photosynthesis in plants"
   - Bad: "Plants"

2. **Use Complete Sentences**
   - Better for AI to understand context
   - Results in higher quality cards

3. **Break Complex Topics**
   - Generate 5-10 cards for major topics
   - Generate 2-3 for subtopics

4. **Review Generated Cards**
   - Check that cards follow single-information principle
   - Edit if needed before adding
   - AI is helpful but not perfect

### Organization Tips

1. **Use Descriptive Deck Names**
   - Format: `Language::Subject::Topic`
   - Example: `English::Literature::Shakespeare`

2. **Filter by AI Tags**
   - Search in Anki: `tag:ai_verified` to see verified cards
   - Use `tag:ai_needs_review` to find cards needing attention
   - Use `tag:ai_from_*` to see generation source

3. **Regular Verification**
   - Verify 5-10 cards weekly
   - Improves card quality over time
   - AI learns your style

## Common Questions

**Q: Why did AI split my card into multiple cards?**
A: The single-information principle means each card should test ONE concept. Complex cards hurt retention. Multiple simple cards work better.

**Q: Can I edit generated cards before adding them?**
A: Preview shows all cards. Editing in preview is planned for future. For now, add them and edit in Anki as needed.

**Q: What if AI generates cards I don't like?**
A: It's normal for AI to need fine-tuning. Edit the cards in Anki after adding. Over time, AI learns your preferences.

**Q: Do I need internet for this?**
A: Yes, AI calls require connection to Google Gemini or Apple cloud services.

**Q: Can I use this offline?**
A: For Apple Intelligence, yes (if on compatible Mac). For Google, no - you need internet.

**Q: How many cards can I generate at once?**
A: 1-20 cards per session. Best results with 5-10 per batch.

**Q: What about my privacy?**
A: Card content is sent to your chosen AI provider. Choose a provider you trust.

## Troubleshooting

### Addon Won't Open
**Problem:** Dialog doesn't appear when clicking menu  
**Solution:**
1. Restart Anki
2. Check config is valid JSON
3. Review Anki console for errors

### No API Key Error
**Problem:** "Missing Gemini API key"  
**Solution:**
1. Get API key from [Google AI Studio](https://aistudio.google.com/app/apikeys)
2. Add to config: `"gemini_api_key": "YOUR_KEY_HERE"`
3. Save and restart Anki

### "Could not complete AI request"
**Problem:** Network or provider error  
**Solution:**
1. Check internet connection
2. Verify API key is correct
3. Try again (might be temporary service issue)

### Generated Cards Not Appearing
**Problem:** Cards don't show in deck after adding  
**Solution:**
1. Restart Anki
2. Check deck name is correct
3. Verify no duplicate note conflicts
4. Check card count increased in deck

### Verification Takes Too Long
**Problem:** "Verifying..." doesn't complete  
**Solution:**
1. Wait longer (can take 30-60 seconds)
2. Try with shorter card text
3. Check internet connection
4. Restart Anki and retry

## Getting Help

- **Addon Issues:** Check the implementation guide
- **Anki Issues:** Visit [Anki Forum](https://forums.ankiweb.net/)
- **AI Quality:** Review output, make suggestions in comments

## System Requirements

- **Anki:** 25.9 or newer
- **Python:** 3.13+
- **OS:** macOS, Windows, Linux
- **Internet:** Required for Google provider (optional for Apple)

## Version History

- **v1.0.0** (Current): Complete refactor with three main features
- **v0.0.1**: Proof-of-concept test dialog

