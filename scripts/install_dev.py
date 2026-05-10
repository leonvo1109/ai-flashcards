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
import argparse
from pathlib import Path

ANKI_ADDONS_DIRS = {
    "darwin": Path.home() / "Library" / "Application Support" / "Anki2" / "addons21",
    "linux": Path.home() / ".local" / "share" / "Anki2" / "addons21",
    "win32": Path.home() / "AppData" / "Roaming" / "Anki2" / "addons21",
}

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
BUILD_SCRIPT = ROOT / "scripts" / "build_all.py"
ADDON_PACKAGE = "ai_flashcards"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install built AI Flashcards .ankiaddon into local Anki addons21."
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Assume build artifacts already exist and do not invoke build script.",
    )
    parser.add_argument(
        "--with-vendor",
        action="store_true",
        help="When build runs, include dependency vendoring (default: skip for faster/more reliable dev loop).",
    )
    return parser.parse_args()


def install_addon(skip_build: bool, with_vendor: bool) -> None:
    system = sys.platform
    addons_dir = ANKI_ADDONS_DIRS.get(system)

    if not addons_dir:
        print(f"Unsupported platform: {system}")
        sys.exit(1)

    if not addons_dir.exists():
        print(f"Anki addons directory not found: {addons_dir}")
        print("Bitte starte zuerst Anki, damit das Verzeichnis erstellt wird.")
        sys.exit(1)

    if not skip_build:
        print(f"Building fresh addon via: {BUILD_SCRIPT}")
        build_cmd = [sys.executable, str(BUILD_SCRIPT)]
        if not with_vendor:
            build_cmd.append("--skip-vendor")
        subprocess.run(build_cmd, check=True)
    else:
        print("Skipping build (--skip-build).")

    addon_file = BUILD_DIR / f"{ADDON_PACKAGE}.ankiaddon"
    if not addon_file.is_file():
        print(f"No .ankiaddon file found at {addon_file}")
        sys.exit(1)

    print(f"Installing into Anki addons dir: {addons_dir}")

    addon_name = addon_file.stem
    addon_dest = addons_dir / addon_name

    print(f"Installing {addon_name}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / addon_name
        try:
            print("  Extracting to temporary directory...")
            with zipfile.ZipFile(addon_file, "r") as zf:
                zf.extractall(tmp_path)
            print("  ✓ Extraction successful")
        except Exception as exc:
            print(f"  ✗ Failed to extract {addon_file}: {exc}")
            print(f"  (Old addon at {addon_dest} remains untouched)")
            sys.exit(1)

        if addon_dest.exists():
            print(f"  Removing old: {addon_dest}")
            try:
                shutil.rmtree(addon_dest)
            except PermissionError as exc:
                print(f"  ✗ Could not replace existing add-on: {exc}")
                print("  Close Anki completely and retry install.")
                sys.exit(1)

        print(f"  Moving to: {addon_dest}")
        shutil.move(str(tmp_path), str(addon_dest))

    print(f"  ✓ {addon_name} installed successfully\n")

    print("Done! Restart Anki to reload addons.")


if __name__ == "__main__":
    args = parse_args()
    install_addon(args.skip_build, args.with_vendor)
