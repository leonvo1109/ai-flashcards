import sys
from pathlib import Path

_addon_dir = Path(__file__).resolve().parent
_lib_dir = _addon_dir / "lib"
if _lib_dir.exists() and str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

from .ui import UI

ui = UI()
