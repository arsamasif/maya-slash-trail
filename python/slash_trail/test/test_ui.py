"""Offscreen tests for the Qt window; skipped when PySide is not installed.

A fake builder and scene stand in for Maya, so the tests check the wiring
between widgets and settings only.

"""

import dataclasses
import importlib.util
import os

import pytest

if not any(importlib.util.find_spec(name) for name in ("PySide6", "PySide2")):
    pytest.skip("PySide is not installed", allow_module_level=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from slash_trail import settings  # noqa: E402
from slash_trail import ui  # noqa: E402


class FakeBuilder:
    def __init__(self):
        self.created = []
        self.deleted = []
        self.selected = []
        self.stored = settings.TrailSettings(base="stored", use_blade=True, tip="storedTip", glow=9.0)

    def create(self, trail_settings):
        trail_settings.validate()
        self.created.append(trail_settings)
        return "|{0}_slashTrail".format(trail_settings.trail_name)

    def rebuild(self, trail, trail_settings=None):
        self.rebuilt = (trail, trail_settings)
        return trail

    def delete(self, trail):
        self.deleted.append(trail)

    def read_settings(self, trail):
        return self.stored

    def selected_trails(self):
        return self.selected

    def fit_to_motion(self, trail_settings, start, end):
        if trail_settings.base == "still":
            raise ValueError("The object does not move")
        self.fitted = (start, end)
        return dataclasses.replace(trail_settings, start=15.0, end=21.0, trail_frames=3.5)


class FakeScene:
    def selection(self):
        return ["|rig|hand_ctl", "|rig|blade_tip"]

    def playback_range(self):
        return (12.0, 40.0)

    def watch_selection(self, callback):
        self.on_selection = callback
        return "watch"

    def unwatch(self, handle):
        self.unwatched = handle


@pytest.fixture
def dialog():
    ui.QtWidgets.QApplication.instance() or ui.QtWidgets.QApplication([])
    return ui.SlashTrailDialog(builder=FakeBuilder(), scene=FakeScene())


def test_settings_round_trip(dialog):
    for wanted in (
        settings.TrailSettings(
            base="a", use_blade=True, tip="b", start=3, end=9, trail_frames=4,
            color=(1.0, 0.0, 0.0), sparks=True,
        ),
        settings.TrailSettings(base="a", width=3.5, facing="y", camera="shotCam"),
    ):
        dialog.set_settings(wanted)
        assert dialog.settings() == wanted


def test_picking_the_object_fits_the_trail_to_its_motion(dialog):
    dialog.use_selection_for(dialog.base_edit)
    current = dialog.settings()
    assert current.base == "|rig|hand_ctl"
    assert (current.start, current.end, current.trail_frames) == (15.0, 21.0, 3.5)
    assert dialog.builder.fitted == (12.0, 40.0)
    assert dialog.status.text() == "Fitted to hand_ctl: frames 15-21, trail 3.5 frames"

    dialog.use_timeline()
    assert (dialog.settings().start, dialog.settings().end) == (12.0, 40.0)


def test_fit_errors_are_reported(dialog):
    dialog.base_edit.setText("still")
    dialog.fit_to_motion()
    assert dialog.status.text() == "The object does not move"


def test_blade_checkbox_switches_fields(dialog):
    assert not dialog.blade_check.isChecked()
    assert dialog.width_spin.isEnabled()
    assert dialog.camera_edit.isEnabled()
    assert not dialog.tip_edit.isEnabled()
    dialog.facing_combo.setCurrentText("x")
    assert not dialog.camera_edit.isEnabled()

    dialog.blade_check.setChecked(True)
    assert not dialog.width_spin.isEnabled()
    assert dialog.tip_edit.isEnabled()
    dialog.tip_edit.setText("")
    assert dialog.axis_combo.isEnabled()
    dialog.tip_edit.setText("tip")
    assert not dialog.axis_combo.isEnabled()


def test_create_reports_errors_and_success(dialog):
    dialog.create()
    assert "Pick an object" in dialog.status.text()
    assert not dialog.builder.created

    dialog.base_edit.setText("sword")
    dialog.end_spin.setValue(20)
    dialog.create()
    assert dialog.status.text() == "Created sword_slashTrail"
    assert dialog.builder.created[0].base == "sword"


def test_selected_actions(dialog):
    dialog.delete_selected()
    assert "Select a trail" in dialog.status.text()

    dialog.builder.selected = ["|sword_slashTrail"]
    dialog.load_selected()
    assert dialog.settings().glow == 9.0
    dialog.rebuild_selected()
    assert dialog.status.text() == "Rebuilt sword_slashTrail"
    dialog.delete_selected()
    assert dialog.builder.deleted == ["|sword_slashTrail"]


def test_selecting_a_trail_loads_it_and_rebuild_uses_the_window(dialog):
    dialog.builder.selected = ["|ball_slashTrail"]
    dialog.scene.on_selection()
    assert dialog.settings().base == "stored"
    assert dialog.status.text().startswith("Editing ball_slashTrail")

    dialog.trail_spin.setValue(40)
    dialog.scene.on_selection()
    assert dialog.settings().trail_frames == 40

    dialog.rebuild_selected()
    trail, used = dialog.builder.rebuilt
    assert trail == "|ball_slashTrail"
    assert used.trail_frames == 40
    assert used.base == "stored"
    assert dialog.status.text() == "Rebuilt ball_slashTrail"


def test_rebuilding_several_trails_uses_their_stored_values(dialog):
    dialog.builder.selected = ["|a_slashTrail", "|b_slashTrail"]
    dialog.rebuild_selected()
    assert dialog.builder.rebuilt == ("|b_slashTrail", None)


def test_closing_stops_watching_the_selection(dialog):
    dialog.close()
    assert dialog.scene.unwatched == "watch"
