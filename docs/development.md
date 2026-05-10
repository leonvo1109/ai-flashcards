# Development

## Daily workflow

```bash
uv sync
uv run hatch run dev-build     # build ai_flashcards
uv run hatch run dev-install   # install ai_flashcards into Anki addons21
# or one-shot:
uv run hatch run install-dev   # build + install all addons via install script
```

Restart Anki to load changes.

Run Anki from the same environment:

```bash
uv run hatch run run-anki
```

Unified CLI (without Hatch wrappers):

```bash
python scripts/dev.py all --addon ai_flashcards
python scripts/dev.py build --addon ai_flashcards --skip-vendor
```

By default, the dev loop skips vendoring for speed.

**What gets bundled:** the `.ankiaddon` zip includes whatever is under `packages/ai_flashcards/lib/`. That folder is gitignored, so it is produced by vendoring.

| Dependency | In `lib/` when |
|------------|----------------|
| `google-genai` (`requirements-runtime.txt`) | After any successful vendoring step (including **GitHub Actions CI** on Ubuntu). |
| `apple-fm-sdk` (`requirements-apple.txt`) | Only when vendoring runs **on macOS** (Swift build). Use `uv run hatch run vendor` locally, or `python scripts/dev.py ... --with-vendor` on a Mac. CI Linux artifacts do **not** include Apple Intelligence bindings. |

Overrides: `ANKI_VENDOR_APPLE_FM=1` (try Apple deps off-macOS, unsupported), `ANKI_SKIP_APPLE_FM=1` (skip Apple on macOS).

Use `--with-vendor` when you need to refresh `lib/` (e.g. before sharing a build that must include Apple support from your machine).

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
