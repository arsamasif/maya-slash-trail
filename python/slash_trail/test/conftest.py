"""Shared pytest setup for the slash_trail tests.

Under ``mayapy`` the Maya tests start ``maya.standalone`` at import time,
which creates a ``QCoreApplication`` that Qt widgets cannot use. Creating
the ``QApplication`` here, before any test module is collected, makes Maya
reuse it so the UI and Maya tests can run in one session.

"""

import importlib.util
import os

if any(importlib.util.find_spec(name) for name in ("PySide6", "PySide2")):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from slash_trail import ui

    QT_APP = ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
