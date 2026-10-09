"""Maya test for the drag-and-drop installer; run with ``mayapy -m pytest``.

Runs the real ``install_slash_trail.py`` entry point against a temporary modules
folder and checks the module file. Shelves do not exist in a standalone
session, so the shelf step must be skipped cleanly. Skipped when Maya is
not importable.

"""

import importlib.util
import os

import pytest

pytest.importorskip("maya.standalone")

import maya.standalone  # noqa: E402

maya.standalone.initialize(name="python")

from slash_trail import install  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))


def test_drop_installer_writes_the_module_file(tmp_path, monkeypatch):
    modules = str(tmp_path / "modules")
    monkeypatch.setattr(install, "user_modules_dir", lambda: modules)
    spec = importlib.util.spec_from_file_location(
        "install_slash_trail", os.path.join(REPO_ROOT, "install_slash_trail.py")
    )
    dropped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dropped)

    dropped.onMayaDroppedPythonFile()

    with open(os.path.join(modules, "slash_trail.mod"), encoding="utf-8") as handle:
        assert handle.read() == install.module_text(REPO_ROOT)


def test_shelf_step_is_skipped_without_shelves():
    assert install.add_shelf_button() is None


def test_user_modules_dir_is_under_the_maya_app_dir():
    assert install.user_modules_dir().replace("\\", "/").endswith("/modules")
