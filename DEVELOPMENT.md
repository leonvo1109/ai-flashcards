# Development Workflow

## Quick Setup

```zsh
# Environment aktualisieren
uv sync

# Add-on bauen
hatch run build

# Add-on bauen + direkt ins Anki-Addons-Verzeichnis installieren
hatch run install-dev
```

Danach Anki neustarten – das Add-on wird mit der neuesten Version geladen.

## Without Hatch

```zsh
# Bauen
python scripts/build_all.py

# Dev-Installieren
python scripts/install_dev.py
```

## Editor-Integration

Wenn du in deinem Editor beim Speichern auto-bauen willst:

```zsh
# Watch-Mode (benötigt watchdog)
while inotifywait -e modify packages/ai_flashcards/*.py; do
  hatch run install-dev
done
```

## Validierung vor Commit

```zsh
hatch run check   # Type-Check + Linting
hatch run fmt     # Auto-Format
```

## Pakete in jeweiliges lib-Verzeichnis installieren

```zsh
ANKI_PYTHON="~/PycharmProjects/anki-add-ons/.venv/bin/python"
"$ANKI_PYTHON" -m pip install --upgrade --target packages/ai_flashcards/lib -r packages/ai_flashcards/requirements-runtime.txt

```
