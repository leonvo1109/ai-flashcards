#!/usr/bin/env python3
"""
Vendors runtime dependencies for each add-on into its lib/ directory.
Uses Anki's Python for ABI compatibility.
"""

import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"


def find_anki_python() -> str:
    env_python = os.environ.get("ANKI_PYTHON")
    if env_python and Path(env_python).exists():
        return env_python

    common_paths = [
        Path.home()
        / "Library"
        / "Application Support"
        / "AnkiProgramFiles"
        / ".venv"
        / "bin"
        / "python",  # macOS Anki
        Path.home() / ".local" / "share" / "Anki" / ".venv" / "bin" / "python",
        Path.home() / "AppData" / "Local" / "Anki" / ".venv" / "Scripts" / "python.exe",
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    return sys.executable


def vendor_addon(addon_dir: Path) -> bool:
    """Vendor dependencies for a single add-on."""
    requirements = addon_dir / "requirements-runtime.txt"

    if not requirements.exists():
        print(f"⊘ {addon_dir.name}: No requirements-runtime.txt, skipping")
        return True

    lib_dir = addon_dir / "lib"
    lib_dir.mkdir(exist_ok=True)

    python_exe = find_anki_python()
    print(f"  Using Python: {python_exe}")
    print(f"  Installing to: {lib_dir}")

    try:
        subprocess.run(
            [
                python_exe,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--target",
                str(lib_dir),
                "-r",
                str(requirements),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✓ {addon_dir.name}: Dependencies vendored successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {addon_dir.name}: Failed to vendor dependencies")
        print(f"  stdout: {e.stdout}")
        print(f"  stderr: {e.stderr}")
        return False


def main():
    print("Vendoring runtime dependencies...\n")

    has_errors = False

    for addon_dir in sorted(p for p in PACKAGES_DIR.iterdir() if p.is_dir()):
        if not vendor_addon(addon_dir):
            has_errors = True

    if has_errors:
        sys.exit("Some add-ons failed to vendor dependencies.")

    print("\nAll dependencies vendored successfully!")


if __name__ == "__main__":
    main()
