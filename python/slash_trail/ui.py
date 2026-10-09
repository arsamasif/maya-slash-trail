"""Qt window for building slash trails while animating.

The window only collects ``TrailSettings`` and hands them to a builder, by
default ``maya_build``. Scene queries (selection, timeline) go through a
small scene object, so the window can be tested offscreen with fakes. It
works with PySide6 (Maya 2025+) and PySide2 (Maya 2024). In Maya, run
``from slash_trail import ui; ui.show()``.

"""

try:
    from PySide6 import QtGui, QtWidgets
except ImportError as pyside6_error:  # Maya 2024 ships PySide2.
    try:
        from PySide2 import QtGui, QtWidgets
    except ImportError:
        # Report why PySide6 failed (often a missing system library), not
        # that the PySide2 fallback is missing too.
        raise pyside6_error from None

from slash_trail import constants
from slash_trail import settings as settings_module

WINDOW_TITLE = "Slash Trail"
OBJECT_NAME = "slashTrailWindow"
ERROR_STYLE = "color: #e06c6c;"
OK_STYLE = "color: #8fc98f;"

_WINDOW = None


class SlashTrailDialog(QtWidgets.QDialog):
    """Pick the blade, set the look, and create or rebuild trails.

    Args:
        builder (module): Object with ``create``, ``rebuild``, ``delete``,
            ``read_settings``, ``selected_trails`` and ``fit_to_motion``.
            Defaults to ``maya_build``.
        scene (object): Object with ``selection()``, ``playback_range()``,
            ``watch_selection(callback)`` and ``unwatch(handle)``. Defaults
            to the Maya scene.
        parent (QWidget): Parent window.

    """

    def __init__(self, builder=None, scene=None, parent=None):
        super().__init__(parent)
        self.builder = builder or _maya_builder()
        self.scene = scene or MayaScene()
        self._color = constants.DEFAULT_COLOR
        self.setObjectName(OBJECT_NAME)
        self.setWindowTitle(WINDOW_TITLE)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._source_box())
        layout.addWidget(self._timing_box())
        layout.addWidget(self._look_box())
        layout.addWidget(self._sparks_box())
        layout.addLayout(self._buttons())
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.set_settings(settings_module.TrailSettings())
        self._loaded_trail = None
        self._selection_watch = self.scene.watch_selection(self.on_selection_changed)

    def closeEvent(self, event):
        """Stop following the Maya selection when the window closes."""
        if self._selection_watch is not None:
            self.scene.unwatch(self._selection_watch)
            self._selection_watch = None
        super().closeEvent(event)

    def on_selection_changed(self):
        """Show the values of a trail as soon as it is selected.

        This way the window always shows what Rebuild Selected will use.

        """
        trails = self.builder.selected_trails()
        if len(trails) != 1 or trails[0] == self._loaded_trail:
            if not trails:
                self._loaded_trail = None
            return
        self._loaded_trail = trails[0]
        self.set_settings(self.builder.read_settings(trails[0]))
        self._report(
            "Editing {0}: change values and press Rebuild Selected".format(_short(trails[0]))
        )

    def settings(self):
        """Read the widgets into settings.

        Returns:
            TrailSettings: Current values.

        """
        return settings_module.TrailSettings(
            base=self.base_edit.text().strip(),
            use_blade=self.blade_check.isChecked(),
            width=self.width_spin.value(),
            facing=self.facing_combo.currentText(),
            camera=self.camera_edit.text().strip(),
            tip=self.tip_edit.text().strip(),
            axis=self.axis_combo.currentText(),
            length=self.length_spin.value(),
            start=self.start_spin.value(),
            end=self.end_spin.value(),
            trail_frames=self.trail_spin.value(),
            substeps=self.substeps_spin.value(),
            inner=self.inner_spin.value(),
            color=self._color,
            glow=self.glow_spin.value(),
            core_white=self.core_spin.value(),
            sparks=self.sparks_box.isChecked(),
            spark_count=self.spark_count_spin.value(),
            spark_speed=self.spark_speed_spin.value(),
            spark_life=self.spark_life_spin.value(),
            seed=self.seed_spin.value(),
        )

    def set_settings(self, settings):
        """Show settings in the widgets.

        Args:
            settings (TrailSettings): Values to show.

        """
        self.base_edit.setText(settings.base)
        self.blade_check.setChecked(settings.use_blade)
        self.width_spin.setValue(settings.width)
        self.facing_combo.setCurrentText(settings.facing)
        self.camera_edit.setText(settings.camera)
        self.tip_edit.setText(settings.tip)
        self.axis_combo.setCurrentText(settings.axis)
        self.length_spin.setValue(settings.length)
        self.start_spin.setValue(settings.start)
        self.end_spin.setValue(settings.end)
        self.trail_spin.setValue(settings.trail_frames)
        self.substeps_spin.setValue(settings.substeps)
        self.inner_spin.setValue(settings.inner)
        self._set_color(settings.color)
        self.glow_spin.setValue(settings.glow)
        self.core_spin.setValue(settings.core_white)
        self.sparks_box.setChecked(settings.sparks)
        self.spark_count_spin.setValue(settings.spark_count)
        self.spark_speed_spin.setValue(settings.spark_speed)
        self.spark_life_spin.setValue(settings.spark_life)
        self.seed_spin.setValue(settings.seed)
        self._update_mode_state()

    def create(self):
        """Build a new trail from the current settings."""
        self._run(lambda: self.builder.create(self.settings()), "Created {0}")

    def rebuild_selected(self):
        """Rebuild the selected trails.

        One selected trail is rebuilt with the values in the window, which
        show that trail's values as soon as it is selected. Several trails
        are each rebuilt from their own stored values, which re-samples
        changed animation.

        """
        trails = self.builder.selected_trails()
        if not trails:
            self._report("Select a trail to rebuild", ok=False)
            return
        if len(trails) == 1:
            current = self.settings()
            self._run(lambda: self._rebuild_one(trails[0], current), "Rebuilt {0}")
            return
        self._run(lambda: [self.builder.rebuild(trail) for trail in trails], "Rebuilt {0}")

    def delete_selected(self):
        """Delete the selected trails."""
        trails = self.builder.selected_trails()
        if not trails:
            self._report("Select a trail to delete", ok=False)
            return
        for trail in trails:
            self.builder.delete(trail)
        self._report("Deleted {0}".format(", ".join(_short(trail) for trail in trails)))

    def load_selected(self):
        """Copy the settings of the selected trail into the window."""
        trails = self.builder.selected_trails()
        if not trails:
            self._report("Select a trail to load its settings", ok=False)
            return
        self.set_settings(self.builder.read_settings(trails[0]))
        self._report("Loaded settings from {0}".format(_short(trails[0])))

    def fit_to_motion(self):
        """Fill timing, width and sparks from how the object moves.

        Looks at the whole playback range, so it also finds the move when
        the start and end fields are still on old values.

        """
        start, end = self.scene.playback_range()
        try:
            fitted = self.builder.fit_to_motion(self.settings(), start, end)
        except (ValueError, RuntimeError) as error:
            self._report(str(error), ok=False)
            return
        self.set_settings(fitted)
        self._report(
            "Fitted to {0}: frames {1:g}-{2:g}, trail {3:g} frames".format(
                _short(fitted.base), fitted.start, fitted.end, fitted.trail_frames
            )
        )

    def use_selection_for(self, edit):
        """Fill a name field with the first selected object.

        Picking the object or the tip also fits the settings to its motion.

        Args:
            edit (QLineEdit): Field to fill.

        """
        selection = self.scene.selection()
        if not selection:
            self._report("Nothing is selected", ok=False)
            return
        edit.setText(selection[0])
        self._update_mode_state()
        if edit in (self.base_edit, self.tip_edit):
            self.fit_to_motion()

    def use_timeline(self):
        """Copy the playback range into the start and end fields."""
        start, end = self.scene.playback_range()
        self.start_spin.setValue(start)
        self.end_spin.setValue(end)

    def pick_color(self):
        """Open a color dialog for the glow color."""
        initial = QtGui.QColor.fromRgbF(*self._color)
        color = QtWidgets.QColorDialog.getColor(initial, self, "Glow color")
        if color.isValid():
            self._set_color((color.redF(), color.greenF(), color.blueF()))

    def _source_box(self):
        box = QtWidgets.QGroupBox("Source")
        form = QtWidgets.QFormLayout(box)
        self.base_edit = QtWidgets.QLineEdit()
        self.base_edit.setPlaceholderText("any animated object (the hilt for a blade)")
        form.addRow("Object", self._with_pick(self.base_edit))

        self.width_spin = _double_spin(0.01, 100000.0, 2)
        self.facing_combo = QtWidgets.QComboBox()
        self.facing_combo.addItems(constants.FACINGS)
        self.facing_combo.currentTextChanged.connect(self._update_mode_state)
        self.camera_edit = QtWidgets.QLineEdit()
        form.addRow("Width", self.width_spin)
        form.addRow("Face", self.facing_combo)
        form.addRow("Camera", self._with_pick(self.camera_edit))

        self.blade_check = QtWidgets.QCheckBox("Use blade (base + tip)")
        self.blade_check.toggled.connect(self._update_mode_state)
        form.addRow(self.blade_check)
        self.tip_edit = QtWidgets.QLineEdit()
        self.tip_edit.setPlaceholderText("optional: blade tip")
        self.tip_edit.textChanged.connect(self._update_mode_state)
        form.addRow("Tip", self._with_pick(self.tip_edit))
        self.axis_combo = QtWidgets.QComboBox()
        self.axis_combo.addItems(constants.AXES)
        self.length_spin = _double_spin(0.01, 100000.0, 2)
        form.addRow("Blade axis", self.axis_combo)
        form.addRow("Blade length", self.length_spin)
        return box

    def _timing_box(self):
        box = QtWidgets.QGroupBox("Timing")
        form = QtWidgets.QFormLayout(box)
        self.start_spin = _double_spin(-100000.0, 100000.0, 2)
        self.end_spin = _double_spin(-100000.0, 100000.0, 2)
        timeline_button = QtWidgets.QPushButton("From timeline")
        timeline_button.clicked.connect(self.use_timeline)
        fit_button = QtWidgets.QPushButton("Fit to motion")
        fit_button.clicked.connect(self.fit_to_motion)
        frames = QtWidgets.QHBoxLayout()
        frames.addWidget(self.start_spin)
        frames.addWidget(self.end_spin)
        frames.addWidget(timeline_button)
        frames.addWidget(fit_button)
        form.addRow("Start / end", frames)
        self.trail_spin = _double_spin(0.1, 1000.0, 1)
        self.substeps_spin = QtWidgets.QSpinBox()
        self.substeps_spin.setRange(1, 32)
        form.addRow("Trail length (frames)", self.trail_spin)
        form.addRow("Samples per frame", self.substeps_spin)
        return box

    def _look_box(self):
        box = QtWidgets.QGroupBox("Look")
        form = QtWidgets.QFormLayout(box)
        self.color_button = QtWidgets.QPushButton()
        self.color_button.clicked.connect(self.pick_color)
        self.glow_spin = _double_spin(0.0, 100.0, 2)
        self.core_spin = _double_spin(0.0, 1.0, 2)
        self.inner_spin = _double_spin(0.0, 0.99, 2)
        form.addRow("Glow color", self.color_button)
        form.addRow("Glow strength", self.glow_spin)
        form.addRow("White-hot edge", self.core_spin)
        form.addRow("Inner edge (0 base, 1 tip)", self.inner_spin)
        return box

    def _sparks_box(self):
        self.sparks_box = QtWidgets.QGroupBox("Sparks")
        self.sparks_box.setCheckable(True)
        form = QtWidgets.QFormLayout(self.sparks_box)
        self.spark_count_spin = QtWidgets.QSpinBox()
        self.spark_count_spin.setRange(1, 500)
        self.spark_speed_spin = _double_spin(0.0, 10000.0, 2)
        self.spark_life_spin = _double_spin(0.1, 1000.0, 1)
        self.seed_spin = QtWidgets.QSpinBox()
        self.seed_spin.setRange(0, 99999)
        form.addRow("Count", self.spark_count_spin)
        form.addRow("Speed (units/frame)", self.spark_speed_spin)
        form.addRow("Life (frames)", self.spark_life_spin)
        form.addRow("Seed", self.seed_spin)
        return self.sparks_box

    def _buttons(self):
        row = QtWidgets.QHBoxLayout()
        for label, slot in (
            ("Create", self.create),
            ("Rebuild Selected", self.rebuild_selected),
            ("Load Selected", self.load_selected),
            ("Delete Selected", self.delete_selected),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        return row

    def _with_pick(self, edit):
        widget = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        button = QtWidgets.QPushButton("<< Selected")
        button.clicked.connect(lambda: self.use_selection_for(edit))
        row.addWidget(edit, 1)
        row.addWidget(button)
        return widget

    def _update_mode_state(self):
        blade = self.blade_check.isChecked()
        uses_axis = blade and not self.tip_edit.text().strip()
        self.tip_edit.setEnabled(blade)
        self.axis_combo.setEnabled(uses_axis)
        self.length_spin.setEnabled(uses_axis)
        self.inner_spin.setEnabled(blade)
        self.width_spin.setEnabled(not blade)
        self.facing_combo.setEnabled(not blade)
        facing_camera = self.facing_combo.currentText() == constants.CAMERA_FACING
        self.camera_edit.setEnabled(not blade and facing_camera)

    def _set_color(self, color):
        self._color = tuple(color)
        self.color_button.setStyleSheet(
            "background-color: {0};".format(QtGui.QColor.fromRgbF(*self._color).name())
        )

    def _run(self, action, message):
        try:
            result = action()
        except (ValueError, RuntimeError) as error:
            self._report(str(error), ok=False)
            return
        names = result if isinstance(result, list) else [result]
        self._report(message.format(", ".join(_short(name) for name in names)))

    def _rebuild_one(self, trail, current):
        rebuilt = self.builder.rebuild(trail, current)
        self._loaded_trail = rebuilt
        return rebuilt

    def _report(self, text, ok=True):
        self.status.setText(text)
        self.status.setStyleSheet(OK_STYLE if ok else ERROR_STYLE)


class MayaScene:
    """Selection and timeline queries against the running Maya session."""

    def selection(self):
        """Return selected transforms.

        Returns:
            list: Long names.

        """
        from maya import cmds

        return cmds.ls(selection=True, long=True, transforms=True) or []

    def playback_range(self):
        """Return the playback range.

        Returns:
            tuple: (start, end) frames.

        """
        from maya import cmds

        return (
            cmds.playbackOptions(query=True, minTime=True),
            cmds.playbackOptions(query=True, maxTime=True),
        )

    def watch_selection(self, callback):
        """Call a function whenever the Maya selection changes.

        Args:
            callback (callable): Function without arguments.

        Returns:
            int: scriptJob number, for ``unwatch``.

        """
        from maya import cmds

        return cmds.scriptJob(event=["SelectionChanged", callback])

    def unwatch(self, handle):
        """Stop a watch started by ``watch_selection``.

        Args:
            handle (int): scriptJob number.

        """
        from maya import cmds

        if cmds.scriptJob(exists=handle):
            cmds.scriptJob(kill=handle, force=True)


def show():
    """Open the window in Maya, replacing one that is already open.

    Returns:
        SlashTrailDialog: The window.

    """
    global _WINDOW
    if _WINDOW is not None:
        _WINDOW.close()
        _WINDOW.deleteLater()
    _WINDOW = SlashTrailDialog(parent=_maya_main_window())
    selection = _WINDOW.scene.selection()
    if _WINDOW.builder.selected_trails():
        _WINDOW.on_selection_changed()
        _WINDOW.show()
        return _WINDOW
    if selection:
        _WINDOW.base_edit.setText(selection[0])
        if len(selection) > 1:
            _WINDOW.blade_check.setChecked(True)
            _WINDOW.tip_edit.setText(selection[1])
    _WINDOW.use_timeline()
    if selection:
        _WINDOW.fit_to_motion()
    _WINDOW.show()
    return _WINDOW


def _maya_builder():
    from slash_trail import maya_build

    return maya_build


def _maya_main_window():
    from maya import OpenMayaUI

    try:
        from shiboken6 import wrapInstance
    except ImportError:
        from shiboken2 import wrapInstance
    pointer = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None


def _double_spin(minimum, maximum, decimals):
    spin = QtWidgets.QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    return spin


def _short(name):
    return name.rsplit("|", 1)[-1]
