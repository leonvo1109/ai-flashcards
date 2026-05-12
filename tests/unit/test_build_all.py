"""Tests for scripts/build_all.py."""

from __future__ import annotations

import json

from scripts import build_all as ba


def test_addon_source_dir_exists():
    assert ba.ADDON_DIR.name == "ai_flashcards"
    assert (ba.ADDON_DIR / "manifest.json").is_file()
    assert (ba.ADDON_DIR / "__init__.py").is_file()


def test_validate_package_missing_required_files(tmp_path):
    pkg = tmp_path / "ai_flashcards"
    pkg.mkdir()

    errs = ba.validate_package(pkg)

    assert errs
    assert any("missing required file" in e for e in errs)


def test_validate_package_manifest_bad_json(tmp_path):
    pkg = tmp_path / "ai_flashcards"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("#\n", encoding="utf-8")
    (pkg / "manifest.json").write_text("{not json", encoding="utf-8")

    errs = ba.validate_package(pkg)
    assert any("valid JSON" in e for e in errs)


def test_validate_package_manifest_package_mismatch(tmp_path):
    pkg = tmp_path / "ai_flashcards"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("#\n", encoding="utf-8")
    (pkg / "manifest.json").write_text(
        json.dumps({"package": "wrong", "name": "Name", "mod": 1}),
        encoding="utf-8",
    )

    errs = ba.validate_package(pkg)
    assert any("package must match directory name" in e for e in errs)


def test_validate_package_manifest_name_empty(tmp_path):
    pkg = tmp_path / "ai_flashcards"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("#\n", encoding="utf-8")
    (pkg / "manifest.json").write_text(
        json.dumps({"package": "ai_flashcards", "name": "   ", "mod": 1}),
        encoding="utf-8",
    )

    errs = ba.validate_package(pkg)
    assert any("name must be" in e for e in errs)


def test_validate_package_manifest_mod_not_int(tmp_path):
    pkg = tmp_path / "ai_flashcards"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("#\n", encoding="utf-8")
    (pkg / "manifest.json").write_text(
        json.dumps({"package": "ai_flashcards", "name": "OK", "mod": "oops"}),
        encoding="utf-8",
    )

    errs = ba.validate_package(pkg)
    assert any("mod must be an integer" in e for e in errs)


def test_build_package_excludes_patterns(monkeypatch, tmp_path):
    pkg = tmp_path / "demo_addon"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("#\n", encoding="utf-8")
    (pkg / "manifest.json").write_text("{}", encoding="utf-8")
    (pkg / "keep.txt").write_text("x", encoding="utf-8")
    (pkg / "skip.pyc").write_text("junk", encoding="utf-8")
    pycache = pkg / "__pycache__"
    pycache.mkdir()
    (pycache / "nope.py").write_text("#", encoding="utf-8")

    out_dir = tmp_path / "build_out"
    out_dir.mkdir()
    monkeypatch.setattr(ba, "BUILD_DIR", out_dir)

    ba.build_package(pkg)

    zip_path = out_dir / "demo_addon.ankiaddon"
    assert zip_path.is_file()

    import zipfile

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "keep.txt" in names
    assert "__pycache__/nope.py" not in names
    assert "skip.pyc" not in names
