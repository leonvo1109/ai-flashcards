#!/usr/bin/env python3
"""
Installiert das gebaute Add-on ins lokale Anki-Addons-Verzeichnis.
Nützlich für schnelle Development-Zyklen.

Sicherheit: Bei Fehlern bleibt das alte Add-on intakt.
"""

import shutil
import sys
import tempfile
import subprocess
import zipfile
from pathlib import Path

ANKI_ADDONS_DIRS = {
    "darwin": Path.home() / "Library" / "Application Support" / "Anki2" / "addons21",
    "linux": Path.home() / ".local" / "share" / "Anki2" / "addons21",
    "win32": Path.home() / "AppData" / "Roaming" / "Anki2" / "addons21",
}

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
BUILD_SCRIPT = ROOT / "scripts" / "build_all.py"


def install_addon() -> None:
    system = sys.platform
    addons_dir = ANKI_ADDONS_DIRS.get(system)

    if not addons_dir:
        print(f"Unsupported platform: {system}")
        sys.exit(1)

    if not addons_dir.exists():
        print(f"Anki addons directory not found: {addons_dir}")
        print("Bitte starte zuerst Anki, damit das Verzeichnis erstellt wird.")
        sys.exit(1)

    print(f"Building fresh addons via: {BUILD_SCRIPT}")
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], check=True)

    addon_files = sorted(BUILD_DIR.glob("*.ankiaddon"))
    if not addon_files:
        print(f"No .ankiaddon files found in {BUILD_DIR}")
        sys.exit(1)

    print(f"Installing into Anki addons dir: {addons_dir}")

    for addon_file in addon_files:
        addon_name = addon_file.stem  # z.B. "ai_flashcards"
        addon_dir = addons_dir / addon_name

        print(f"Installing {addon_name}...")

        # 1. In temporäres Verzeichnis entpacken (sicher vor Fehlern)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / addon_name
            try:
                print(f"  Extracting to temporary directory...")
                with zipfile.ZipFile(addon_file, "r") as zf:
                    zf.extractall(tmp_path)
                print(f"  ✓ Extraction successful")
            except Exception as exc:
                print(f"  ✗ Failed to extract {addon_file}: {exc}")
                print(f"  (Old addon at {addon_dir} remains untouched)")
                sys.exit(1)

            # 2. Altes Add-on nur jetzt ersetzen (wenn neues valide ist)
            if addon_dir.exists():
                print(f"  Removing old: {addon_dir}")
                shutil.rmtree(addon_dir)

            # 3. Neues Add-on installieren
            print(f"  Moving to: {addon_dir}")
            shutil.move(str(tmp_path), str(addon_dir))

        print(f"  ✓ {addon_name} installed successfully\n")

    print("Done! Restart Anki to reload addons.")


if __name__ == "__main__":
    install_addon()
