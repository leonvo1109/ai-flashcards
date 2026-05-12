# Agent and contributor notes

This repository is the **AI Flashcards** Anki add-on. Runtime code lives under [`ai_flashcards/`](ai_flashcards/); distribution assets (`manifest.json`, optional `lib/` from vendoring) ship inside that folder.

## Imports and tests

- **`AI_FLASHCARDS_LITE_IMPORT=1`** — When set (see [`tests/conftest.py`](tests/conftest.py)), importing `ai_flashcards` does **not** register Qt hooks or construct UI. Pytest sets this before loading app code.
- Prefer **`from ai_flashcards…`** in tests; shared doubles live in **`tests/support/`**.
- Automated tests are **`tests/unit/test_*.py`** (pytest discovers them via `testpaths = ["tests"]`).

## Layout

| Path | Role |
|------|------|
| `ai_flashcards/` | Add-on package (services, UI, `llm/` providers, Anki bridge) |
| `scripts/` | Build, install, vendor CLI (`build_all.py`, `dev.py`, …) |
| `tests/unit/` | Pytest modules |
| `tests/support/` | Test helpers (e.g. fake LLM) |
| `docs/` | Contributor documentation |

## Tooling

Use **[uv](https://docs.astral.sh/uv/)** as the primary driver.

```bash
uv sync --all-groups          # runtime + dev (pytest, ruff, black)
uv run pytest tests/
uv run ruff check ai_flashcards scripts tests runanki.py
uv run black --check ai_flashcards scripts tests runanki.py
```

[Hatch](https://hatch.pypa.io/) wrappers (`uv run hatch run …`) remain documented in [`docs/development.md`](docs/development.md).

Style: **Python 3.13+**, **Black** (88 cols), **Ruff** rules configured in [`pyproject.toml`](pyproject.toml).
