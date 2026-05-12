# AI Flashcards (Anki add-on)

Repository for **AI Flashcards**, an [Anki](https://apps.ankiweb.net/) add-on: verify cards, create variants, and generate from content using **Google Gemini** or **Apple Intelligence** (macOS). Source lives in [`ai_flashcards/`](ai_flashcards/); see [`ai_flashcards/README.md`](ai_flashcards/README.md) for configuration and menus.

## Quick start (contributors)

**Requirements:** Python **3.13+**, [uv](https://docs.astral.sh/uv/), Anki **25.9+**.

```bash
git clone git@github.com:leonvo1109/ai-flashcards.git
cd ai-flashcards
uv sync
uv run hatch run dev-build
uv run hatch run dev-install
```

Restart Anki after installing.

### One-click inside Cursor

- Open **Run and Debug** and choose `Run Anki (AI Flashcards dev loop)`.
- Click the green run button.
- It executes: build → install → launch Anki.

**More detail:** [docs/development.md](docs/development.md) (env vars, manual build, format/lint).

## Layout

```
ai-flashcards/
├── ai_flashcards/       # Add-on source + manifest.json
├── scripts/             # build_all.py, install_dev.py, vendor_dependencies.py
├── tests/
│   ├── unit/            # pytest modules (test_*.py)
│   └── support/         # shared test helpers / fakes
├── docs/                # Contributor docs (see docs/development.md)
├── AGENTS.md            # Repo orientation for contributors & tooling
└── .github/workflows/   # CI → tests + build artifact
```

## License

[MIT](LICENSE.md)
