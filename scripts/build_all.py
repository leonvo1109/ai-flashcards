from pathlib import Path
import json
import zipfile
import subprocess
import sys
import argparse

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"
BUILD_DIR = ROOT / "build"

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".venv",
    "venv",
}

EXCLUDE_FILES = {
    ".DS_Store",
    "pyproject.toml",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
}

REQUIRED_FILES = {"__init__.py", "manifest.json"}


def validate_package(pkg_dir: Path) -> list[str]:
    errors: list[str] = []

    for file_name in REQUIRED_FILES:
        if not (pkg_dir / file_name).is_file():
            errors.append(f"missing required file: {file_name}")

    manifest_path = pkg_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"manifest.json is not valid JSON: {exc}")
        else:
            if manifest.get("package") != pkg_dir.name:
                errors.append(
                    "manifest package must match directory name "
                    f"({manifest.get('package')!r} != {pkg_dir.name!r})"
                )
            if (
                not isinstance(manifest.get("name"), str)
                or not manifest["name"].strip()
            ):
                errors.append("manifest name must be a non-empty string")
            if not isinstance(manifest.get("mod"), int):
                errors.append("manifest mod must be an integer")

    return errors


def vendor_dependencies() -> None:
    """Run vendor_dependencies.py before building."""
    print("Vendoring dependencies...\n")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vendor_dependencies.py")], check=False
    )
    if result.returncode != 0:
        raise SystemExit("Dependency vendoring failed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build .ankiaddon archives from packages/")
    parser.add_argument(
        "--addon",
        help="Build only one add-on (folder name under packages/), e.g. ai_flashcards",
    )
    parser.add_argument(
        "--skip-vendor",
        action="store_true",
        help="Skip vendoring runtime dependencies before building.",
    )
    return parser.parse_args()


def iter_packages(addon: str | None) -> list[Path]:
    packages = sorted(p for p in PACKAGES_DIR.iterdir() if p.is_dir())
    if addon is None:
        return packages
    filtered = [p for p in packages if p.name == addon]
    if not filtered:
        raise SystemExit(f"Unknown add-on: {addon!r}. Available: {', '.join(p.name for p in packages)}")
    return filtered


def build_package(pkg_dir: Path) -> None:
    zip_path = BUILD_DIR / f"{pkg_dir.name}.ankiaddon"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in pkg_dir.rglob("*"):
            rel = path.relative_to(pkg_dir)
            if path.is_dir():
                continue
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue
            if path.name in EXCLUDE_FILES:
                continue
            if path.suffix in EXCLUDE_SUFFIXES:
                continue
            zf.write(path, rel.as_posix())

    print(f"Built: {zip_path}")


def main() -> None:
    args = parse_args()
    BUILD_DIR.mkdir(exist_ok=True)

    if not args.skip_vendor:
        vendor_dependencies()
    else:
        print("Skipping vendoring (--skip-vendor).")

    print("\nBuilding add-ons...\n")
    has_errors = False

    for pkg_dir in iter_packages(args.addon):
        validation_errors = validate_package(pkg_dir)
        if validation_errors:
            has_errors = True
            print(f"Invalid package: {pkg_dir.name}")
            for err in validation_errors:
                print(f"  - {err}")
            continue
        build_package(pkg_dir)

    if has_errors:
        raise SystemExit("Build failed due to package validation errors.")


if __name__ == "__main__":
    main()
