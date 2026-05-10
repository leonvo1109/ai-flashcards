#!/usr/bin/env python3
"""
Vendors runtime dependencies for each add-on into its lib/ directory.
Uses Anki's Python for ABI compatibility.
"""

import subprocess
import sys
import os
import platform
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


def _pip_install_target(
    python_exe: str, lib_dir: Path, requirements_file: Path
) -> None:
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
            str(requirements_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def vendor_addon(addon_dir: Path) -> bool:
    """Vendor dependencies for a single add-on.

    Cross-platform libs come from ``requirements-runtime.txt`` (currently ``google-genai``).

    Optional ``requirements-apple.txt`` installs only on macOS (``apple-fm-sdk`` Swift build).

    Override: set ``ANKI_VENDOR_APPLE_FM=1`` to attempt Apple deps on non-macOS (unsupported).
    """
    runtime_req = addon_dir / "requirements-runtime.txt"
    apple_req = addon_dir / "requirements-apple.txt"

    if not runtime_req.exists() and not apple_req.exists():
        print(f"⊘ {addon_dir.name}: No vendor requirements files, skipping")
        return True

    lib_dir = addon_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)

    python_exe = find_anki_python()
    print(f"  Using Python: {python_exe}")
    print(f"  Installing to: {lib_dir}")

    try:
        if runtime_req.exists():
            print(f"  requirements: {runtime_req.name}")
            _pip_install_target(python_exe, lib_dir, runtime_req)

        should_vendor_apple = platform.system() == "Darwin"
        force_apple = os.environ.get("ANKI_VENDOR_APPLE_FM", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        skip_apple = os.environ.get("ANKI_SKIP_APPLE_FM", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )

        if (
            apple_req.exists()
            and not skip_apple
            and (should_vendor_apple or force_apple)
        ):
            ctx = "" if should_vendor_apple else " (ANKI_VENDOR_APPLE_FM)"
            print(f"  Apple SDK requirements{ctx}: {apple_req.name}")
            _pip_install_target(python_exe, lib_dir, apple_req)
        elif apple_req.exists() and not should_vendor_apple and not skip_apple:
            print(f"⊘ Skipping {apple_req.name} (Apple SDK only installs on macOS)")

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
