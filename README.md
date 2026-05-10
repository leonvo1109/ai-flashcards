# anki-add-ons

Monorepo for [Anki](https://apps.ankiweb.net/) add-ons: build scripts, CI, and packaged `.ankiaddon` outputs.

## Add-ons in this repo

| Add-on | Folder | What it does |
|--------|--------|----------------|
| **AI Flashcards** | [`packages/ai_flashcards/`](packages/ai_flashcards/) | Verify cards, create variants, and generate from content using **Google Gemini** or **Apple Intelligence** (macOS). |

Open the add-on folder README for configuration, menu paths, and source map.

## Quick start (contributors)

**Requirements:** Python **3.13+**, [uv](https://docs.astral.sh/uv/), Anki **25.9+**.

```bash
git clone <your-repo-url>
cd anki-add-ons
uv sync
uv run hatch run dev-build
uv run hatch run dev-install
```

Restart Anki after installing.

### One-click inside Cursor

- Open **Run and Debug** and choose `Run Anki (AI Flashcards dev loop)`.
- Click the green run button.
- It executes: build -> install -> launch Anki for `ai_flashcards`.

**More detail:** [docs/development.md](docs/development.md) (env vars, manual build, format/lint).

## Layout

```
anki-add-ons/
├── packages/<addon-name>/   # Add-on source + manifest.json
├── scripts/                 # build_all.py, install_dev.py, vendor_dependencies.py
├── docs/                    # Contributor docs only
└── .github/workflows/       # CI → build artifacts
```

## License

[MIT](LICENSE.md)
