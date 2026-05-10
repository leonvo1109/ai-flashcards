"""Tests for scripts/vendor_dependencies.py."""

from __future__ import annotations

import os
from subprocess import CalledProcessError

from scripts import vendor_dependencies as vd


def test_find_anki_python_explicit_env(monkeypatch, tmp_path):
    exe = tmp_path / "fake-python"
    exe.write_text("", encoding="utf-8")

    monkeypatch.setenv("ANKI_PYTHON", str(exe))

    assert vd.find_anki_python() == str(exe)


def test_find_anki_python_missing_env_fallback_executable(monkeypatch):
    monkeypatch.delenv("ANKI_PYTHON", raising=False)

    resolved = vd.find_anki_python()

    assert os.path.isfile(resolved) or os.path.exists(resolved)


def test_vendor_addon_no_req_files_returns_true(tmp_path):
    addon = tmp_path / "empty_addon"
    addon.mkdir()

    assert vd.vendor_addon(addon) is True


def test_vendor_addon_runs_runtime_and_calls_pip(monkeypatch, tmp_path):
    addon = tmp_path / "a"
    addon.mkdir()
    (addon / "requirements-runtime.txt").write_text("# empty\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_pip(py: str, lib: object, rf: object) -> None:
        captured["python"] = py
        captured["lib"] = lib
        captured["req"] = rf

    monkeypatch.setattr(vd, "_pip_install_target", fake_pip)
    monkeypatch.setattr(vd.platform, "system", lambda: "Linux")

    assert vd.vendor_addon(addon) is True

    assert captured["req"] == addon / "requirements-runtime.txt"


def test_vendor_addon_handles_pip_failure(monkeypatch, tmp_path):
    addon = tmp_path / "a"
    addon.mkdir()
    (addon / "requirements-runtime.txt").write_text("x\n", encoding="utf-8")

    def boom(*_args: object, **_kwargs: object):
        raise CalledProcessError(returncode=1, cmd="pip", output="", stderr="err")

    monkeypatch.setattr(vd, "_pip_install_target", boom)

    assert vd.vendor_addon(addon) is False


def test_vendor_addon_apple_skip_non_darwin(monkeypatch, tmp_path):
    addon = tmp_path / "macish"
    addon.mkdir()
    (addon / "requirements-apple.txt").write_text("apple-dep\n", encoding="utf-8")

    monkeypatch.setattr(vd.platform, "system", lambda: "Linux")

    calls = []

    def record(*args: object, **_kwargs: object):
        calls.append(args)

    monkeypatch.setattr(vd, "_pip_install_target", record)

    assert vd.vendor_addon(addon) is True
    assert calls == []


def test_vendor_addon_apple_installed_when_forced(monkeypatch, tmp_path):
    addon = tmp_path / "a"
    addon.mkdir()
    (addon / "requirements-apple.txt").write_text("apple\n", encoding="utf-8")

    monkeypatch.setenv("ANKI_VENDOR_APPLE_FM", "1")
    monkeypatch.delenv("ANKI_SKIP_APPLE_FM", raising=False)
    monkeypatch.setattr(vd.platform, "system", lambda: "Linux")

    targets = []

    def record(_py: str, _lib_dir: object, rf: object):
        targets.append(getattr(rf, "name", str(rf)))

    monkeypatch.setattr(vd, "_pip_install_target", record)

    assert vd.vendor_addon(addon) is True

    assert "requirements-apple.txt" in targets


def test_vendor_addon_apple_skipped_when_env_set(monkeypatch, tmp_path):
    addon = tmp_path / "a"
    addon.mkdir()
    (addon / "requirements-apple.txt").write_text("apple\n", encoding="utf-8")

    monkeypatch.setenv("ANKI_SKIP_APPLE_FM", "1")
    monkeypatch.delenv("ANKI_VENDOR_APPLE_FM", raising=False)
    monkeypatch.setattr(vd.platform, "system", lambda: "Darwin")

    calls = []

    def record(*args: object, **_kwargs: object):
        calls.append(1)

    monkeypatch.setattr(vd, "_pip_install_target", record)

    assert vd.vendor_addon(addon) is True
    assert calls == []
