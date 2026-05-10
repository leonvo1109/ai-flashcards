# Development

## Daily workflow

```bash
uv sync
uv run hatch run install-dev   # builds, then installs the .ankiaddon into Anki
```

Restart Anki to load changes.

Without Hatch:

```bash
python scripts/build_all.py
python scripts/install_dev.py
```

Build output: `build/<addon_name>.ankiaddon`.

## Format and lint

```bash
uv run hatch run fmt    # black + ruff --fix
uv run hatch run check  # black --check, ruff, mypy (mypy may include vendored lib noise)
```

## Environment variables (AI Flashcards)

Optional overrides for local dev. Do not commit secrets.

Copy the example file and edit:

```bash
cp .env.example .env
```

| Variable | Used for |
|----------|-----------|
| `GOOGLE_API_KEY` | Gemini when `gemini_api_key` in add-on config is empty ([`GoogleProvider`](../packages/ai_flashcards/llm/providers/google_provider.py)) |

Running Anki from the repo (if you use `runanki.py`), load env first, e.g.:

```bash
set -a && source .env && set +a && uv run python runanki.py
```

`.env` is gitignored; only `.env.example` is tracked.

## Vendoring runtime deps into the add-on

Some dependencies are bundled under `packages/ai_flashcards/lib/` for distribution:

```bash
uv run hatch run vendor
```

## Optional: rebuild on save (Linux example)

```bash
while inotifywait -e modify packages/ai_flashcards/*.py; do uv run hatch run install-dev; done
```
