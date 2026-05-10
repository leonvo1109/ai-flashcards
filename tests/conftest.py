"""Pytest-local setup (runs before importing test modules)."""

from __future__ import annotations

import os

os.environ.setdefault("AI_FLASHCARDS_LITE_IMPORT", "1")
