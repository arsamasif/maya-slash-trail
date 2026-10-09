"""Tests for slash_trail.install that do not need Maya."""

import os
import sys

import pytest

from slash_trail import __version__
from slash_trail import install

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))


def test_module_text_points_at_the_repo_with_forward_slashes():
    text = install.module_text(r"C:\tools\maya-slash-trail")
    first, second = text.splitlines()
    assert first.startswith("+ slash_trail {0} ".format(__version__))
    assert first.endswith("/tools/maya-slash-trail")
    assert "\\" not in first
    assert second == "PYTHONPATH +:= python"


def test_write_module_file_creates_the_folder_and_overwrites(tmp_path):
    modules = str(tmp_path / "maya" / "modules")
    path = install.write_module_file(REPO_ROOT, modules)
    assert path == os.path.join(modules, "slash_trail.mod")
    with open(path, encoding="utf-8") as handle:
        assert handle.read() == install.module_text(REPO_ROOT)
    assert install.write_module_file(REPO_ROOT, modules) == path


def test_write_module_file_rejects_a_wrong_folder(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing slash_trail package"):
        install.write_module_file(str(tmp_path), str(tmp_path / "modules"))


def test_add_to_session_adds_the_python_folder_once(monkeypatch):
    package_dir = os.path.normpath(os.path.join(REPO_ROOT, "python"))
    others = [entry for entry in sys.path if os.path.normpath(entry) != package_dir]
    monkeypatch.setattr(sys, "path", others)
    python_dir = install.add_to_session(REPO_ROOT)
    install.add_to_session(REPO_ROOT)
    normalized = [os.path.normpath(entry) for entry in sys.path]
    assert normalized.count(python_dir) == 1
    assert os.path.isdir(os.path.join(python_dir, "slash_trail"))
