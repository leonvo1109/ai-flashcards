import os
import sys
from pathlib import Path

_addon_dir = Path(__file__).resolve().parent
_lib_dir = _addon_dir / "lib"
# Prepend bundled wheels only in normal Anki runs. Pytest sets AI_FLASHCARDS_LITE_IMPORT=1
# so `google.*` resolves to the environment's google-genai instead of a stale vendored tree.
if (
    _lib_dir.exists()
    and os.getenv("AI_FLASHCARDS_LITE_IMPORT") != "1"
    and str(_lib_dir) not in sys.path
):
    sys.path.insert(0, str(_lib_dir))


if os.getenv("AI_FLASHCARDS_LITE_IMPORT") == "1":
    # Tests / tooling import submodules only; avoid Qt/Anki UI bootstrap here.
    pass
else:
    try:
        import nest_asyncio

        nest_asyncio.apply()
    except ImportError:
        pass

    from aqt import gui_hooks  # noqa: E402

    from .ui_enhanced import EnhancedUI  # noqa: E402

    ui = EnhancedUI()

    # Add hooks to make the add-on accessible from different contexts
    def _register_hooks():
        """Register Anki hooks to make the add-on available from different contexts."""
        gui_hooks.main_window_setup_ui.append(ui.setup_context_menu_items)

    try:
        _register_hooks()
    except Exception as e:
        print(f"[AI Flashcards] Error registering hooks: {e}")
