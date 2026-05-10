#!/usr/bin/env python3
"""Local development entrypoint for AI Flashcards."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = ROOT / "scripts" / "build_all.py"
INSTALL_SCRIPT = ROOT / "scripts" / "install_dev.py"
RUN_SCRIPT = ROOT / "runanki.py"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Easy dev workflow: build/install/run AI Flashcards."
    )
    parser.add_argument(
        "action",
        choices=["build", "install", "run", "all"],
        help="'all' = build -> install -> run",
    )
    parser.add_argument(
        "--skip-vendor",
        action="store_true",
        help="Skip vendoring dependencies during build.",
    )
    parser.add_argument(
        "--with-vendor",
        action="store_true",
        help="Include vendoring dependencies during build/install (default is skip in dev).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    py = sys.executable

    if args.action in {"build", "all"}:
        cmd = [py, str(BUILD_SCRIPT)]
        should_skip_vendor = args.skip_vendor or not args.with_vendor
        if should_skip_vendor:
            cmd.append("--skip-vendor")
        run(cmd)

    if args.action in {"install", "all"}:
        cmd = [py, str(INSTALL_SCRIPT)]
        if args.action == "all":
            cmd.append("--skip-build")
        if args.with_vendor:
            cmd.append("--with-vendor")
        run(cmd)

    if args.action in {"run", "all"}:
        run([py, str(RUN_SCRIPT)])


if __name__ == "__main__":
    main()
