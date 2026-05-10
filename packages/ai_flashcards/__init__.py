import sys
from pathlib import Path

try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

_addon_dir = Path(__file__).resolve().parent
_lib_dir = _addon_dir / "lib"
if _lib_dir.exists() and str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

from .ui_enhanced import EnhancedUI  # noqa: E402
from aqt import gui_hooks  # noqa: E402

ui = EnhancedUI()


# Add hooks to make the add-on accessible from different contexts
def _register_hooks():
    """Register Anki hooks to make the add-on available from different contexts."""
    # Hook into main window setup to add keyboard shortcuts
    gui_hooks.main_window_setup_ui.append(ui.setup_context_menu_items)


try:
    _register_hooks()
except Exception as e:
    print(f"[AI Flashcards] Error registering hooks: {e}")
