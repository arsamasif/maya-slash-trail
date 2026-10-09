# slash-trail walkthrough

This document explains how the code works, file by file, and why it is
built the way it is.

## 1. The idea in one paragraph

A slash trail is a ribbon swept by a moving object. Instead of creating new
geometry every frame, the tool samples the object once over the whole move,
builds **one** static ribbon mesh that covers the full path, and lets the
shader show only a moving window of it. U on the ribbon runs along time,
V runs across it. A ramp on U, placed with a keyed `place2dTexture` frame,
is opaque just behind the object and fades to nothing a few frames later;
outside that window Maya returns the ramp's default color (black, so
transparent). A second ramp on V shapes the trail across its width.

There are two ways to get the ribbon's two edges:

- **Point trail (default):** follow one object's pivot and offset it by half
  the width on each side. The side direction is turned towards a camera at
  every sample, or taken from one of the object's own axes. The V ramp is
  brightest in the middle, so it reads as a comet tail or motion streak.
- **Blade trail (`use_blade`):** use a blade base and tip (a second object,
  or an axis and length). The V ramp is brightest near the tip, which gives
  the crescent of a sword slash.

```
TrailSettings ──validate──► ribbon.sample_times ──► maya_sample.sample
                                                        │ (edge A, edge B) per sample
                                                        ▼
                      ribbon.build ◄────────────────────┤
                           │                            ▼
                     maya_build._create_mesh      sparks.generate
                           │                            │
             _create_trail_shader + reveal.keys    _create_sparks + _key_spark
                           └─────────► trail group ◄────┘
                                (settings JSON + shading connections)
```

## 2. How to run it

- In Maya: `from slash_trail import ui; ui.show()`. Selecting one object
  first fills it in. Selecting two (hilt, then tip) also switches on blade
  mode. The window copies the timeline range.
- From a script: `maya_build.create(settings.TrailSettings(...))`, then
  `maya_build.rebuild(group)` or `maya_build.delete(group)`.
- Tests: `pytest` for everything that does not need Maya (60 tests, plus 9 UI
  tests when PySide6 is installed). `mayapy -m pytest` runs all 84, including
  15 that sample, fit and build real trails and run the installer in
  `maya.standalone`.
- Install for a user: drag `install_slash_trail.py` into the Maya viewport.

## 3. File by file

### `package.py`, `pyproject.toml`, `.github/workflows/tests.yml`

Rez package (puts `python/` on `PYTHONPATH`) and a pip-installable project
with `test` and `ui` extras. CI installs both extras and runs pytest on
Linux; the Maya tests skip there because `maya.standalone` is not
importable.

### `python/slash_trail/__init__.py`

Package docstring and `__version__`.

### `constants.py`

Defaults for every setting, the allowed blade axes, a `MAX_SAMPLES` guard
(so a typo in the range cannot create a huge mesh), node and attribute
names, and the three gradients used by the shader:

- `AGE_GRADIENT`: opacity from the tail (0) to the blade (1);
- `EDGE_GRADIENT`: opacity from the inner edge (0) to the blade tip (1),
  peaking just before the tip so a blade trail reads as a crescent;
- `CENTER_EDGE_GRADIENT`: opacity across a point trail, peaking in the
  middle and fading to both edges;
- `CORE_GRADIENT`: emission brightness across the blade.

`FACINGS` lists how a point trail can orient its width: `"camera"` or one
of the object's axes.

`SPARK_STREAK_FRAMES` and `SPARK_WIDTH_RATIO` size a spark streak from its
speed, so faster sparks get longer streaks, like motion blur.

### `settings.py`

`TrailSettings` is a dataclass holding every input: the driving object
(`base`), the mode switch (`use_blade`), point-trail fields (`width`,
`facing`, `camera`), blade fields (`tip`, or `axis` + `length` when there
is no tip), timing (`start`, `end`, `trail_frames`, `substeps`), look
(`inner`, `color`, `glow`, `core_white`) and sparks (`sparks`,
`spark_count`, `spark_speed`, `spark_life`, `seed`).

- `validate()` raises a `ValueError` with a message aimed at the animator
  ("End frame must be after the start frame"). The UI shows that message.
  It only checks the fields of the active mode (`_validate_blade` or
  `_validate_point`), so leftover blade values do not block a point trail.
- `sample_count` and `trail_name` are derived properties. `trail_name`
  strips DAG path and namespace separators so the group gets a legal name.
- `to_json()` / `from_json()` store the settings on the trail group.
  `from_json` ignores unknown keys so a trail built by a newer version
  still rebuilds in an older one. Settings saved before `use_blade`
  existed were always blade trails, so `from_json` defaults the flag to
  `True` for them, while new settings default to a point trail.

### `vecmath.py`

`add`, `sub`, `scale`, `lerp`, `dot`, `cross`, `length`, `normalize` on
plain tuples. The core needs very little math, so it uses no numpy and no
Maya types, and it runs anywhere pytest runs.

### `ribbon.py`

- `sample_times(start, end, substeps)` returns evenly spaced frames with
  both ends included.
- `blade_tips(base_points, base_axes, length)` derives tips from a
  direction (the Maya side does the same thing inline for the one-object
  mode).
- `camera_sides(centers, eye_points)` gives the width direction of a
  camera-facing point trail: `cross(tangent, view)`, where the tangent is a
  central difference of the path and the view runs from the camera to the
  object. A side perpendicular to both the motion and the line of sight
  makes the ribbon lie flat towards the camera. If the object stands still,
  or moves straight at the camera, the cross product is zero and the
  previous side is reused so the ribbon does not flip.
- `point_edges(centers, sides, width)` offsets each centre by half the width
  both ways. The two edges go into `build` as "base" and "tip" with
  `inner=0`, so both modes share one mesh builder.
- `swept_distance(points, window)` is a sliding-window sum of step lengths:
  the longest path the tip covers in any run of `window` samples.
- `short_trail_warning(...)` compares that distance (for a window as long as
  the trail) with the ribbon width. If the tip moves less than the ribbon is
  wide, the visible trail would sit inside the object, so it returns a
  warning text. This came from a real test: a 1-unit cube sliding 10 units
  over 120 frames left a 0.5-unit trail completely hidden inside the cube.
- `build(base_points, tip_points, inner)` returns a `RibbonMesh` laid out the
  way `MFnMesh.create` wants it. Each sample is one column of two vertices:
  index `2i` is the inner edge (`lerp(base, tip, inner)`), `2i + 1` is the tip.
  Quad `i` is `(2i, 2i+2, 2i+3, 2i+1)`. There is one UV per vertex, so the
  UV ids equal the vertex ids. U is `i / last`, V is 0 inside and 1 at the tip.

### `auto.py`

`suggest(times, positions, size)` turns one sample per frame of the leading
point (the pivot, or the blade tip) and the object's size into a
`Suggestion`, so the first trail is visible without tweaking:

- **Range:** per-frame speeds; frames slower than `MOVING_FRACTION` (15%) of
  the top speed count as standing still, and the range is cropped to the
  first and last moving frame.
- **Trail length:** `TRAIL_SIZES * size / mean_speed`, so the visible trail
  is about three object sizes long at the average speed. It is clamped to
  2-24 frames and snapped to half frames.
- **Samples per frame:** enough that one sample step is at most 20% of the
  object size at top speed (`ceil(peak / (0.2 * size))`), capped at 16 and
  lowered if it would exceed `MAX_SAMPLES`.
- **Width and sparks:** width is 0.75 of the size; spark speed is half the
  mean speed and spark life 1.5 trail lengths.
- Objects with no size of their own (a locator, a joint) use 5% of the path
  length. An object that never moves is a `ValueError`.

`apply(settings, suggestion)` returns a copy with only those fields changed
(`dataclasses.replace`), so the object, colors and other choices are kept.

This came from a real case: a 1-unit cube sliding 10 units over 120 frames
with the default 6-frame trail left about 0.5 units of trail, all inside the
cube. Fitted, it gets a 24-frame trail 1.3 units wide that shows clearly
behind it.

### `reveal.py`

This module holds the core trick. `place2dTexture` maps surface U into
texture space with `(u - translateFrameU) / coverageU`, and with `wrapU` off
anything outside 0-1 returns the default color. For a ribbon from `start` to
`end` (`D = end - start`) and a trail of `L` frames, at frame `c` the window
is:

```
coverageU       = L / D
translateFrameU = (c - L - start) / D
```

`translateFrameU` is linear in `c`, so two linear keys animate it exactly:

- at `start` the window ends at U = 0, so nothing is visible yet;
- at `end + L` the window starts at U = 1, so the tail has drained out.

`ramp_position()` mirrors the Maya formula. It lets the pure tests prove
that the blade sits at ramp position 1, the tail at 0, and that future or
old parts of the ribbon fall outside 0-1. The Maya test then checks that
`colorAtPoint` agrees with it.

### `sparks.py`

- `generate()` uses `random.Random(seed)`, so a rebuild gives the same
  sparks. Each spark picks a sample, starts 85-100% of the way to the tip,
  and flies along the tip's direction of motion plus an outward push
  (`OUTWARD_PUSH`) and some jitter (`JITTER`). Speed and life vary per
  spark. The normal of the swing plane (`cross(tangent, outward)`) is stored
  so the streak can face the swing.
- `Spark.end_position` is `position + velocity * life`.
- `streak()` builds a single quad in the spark's local space. It points
  backwards from the head along the velocity, with U = 0 at the tail and 1
  at the head. It reuses `ribbon.build` with `inner=0` so there is one mesh
  layout in the code base.

### `maya_sample.py` (Maya API 2.0)

`sample(settings, times)` returns the two ribbon edges per sample for either
mode. It finds the `worldMatrix[0]` plug of each object it needs and
evaluates it with `plug.asMObject(MDGContext(MTime(t)))` for each sample
time. Key decisions:

- **No timeline scrubbing.** Evaluating in a context leaves the current
  frame alone. That is faster, avoids triggering viewport refreshes, and
  works at sub-frame times.
- **Anything that drives the object works**, because the world matrix is
  evaluated through the DG: keys, constraints, IK, parents.
- **Blade mode** (`_sample_blade`): base and tip positions. Without a tip
  object, the rows of a Maya world matrix are the object's axes in world
  space, so the tip is `translation + row * length` (`_point_along_axis`).
- **Point mode** (`_sample_point`): the object's position, plus either the
  camera's position at the same time (so a moving camera is handled) or the
  object's chosen axis (`_axis`). The pure `ribbon.camera_sides` and
  `ribbon.point_edges` then turn those into the two edges.
- `motion(settings, times)` returns the leading point per time and a size
  for `auto`: the tip and the longest blade length for a blade, or the pivot
  and the world bounding-box diagonal (`cmds.exactWorldBoundingBox`) for a
  point trail.
- Missing objects become a `ValueError` the UI can show.

### `maya_build.py`

- `create(settings)`: validate, sample, warn through
  `MGlobal.displayWarning` if `ribbon.short_trail_warning` says the trail
  will be hidden, build the ribbon (`inner` only applies to blades; point
  trails use 0 so the ribbon spans both edges), create the group,
  mesh, trail shader and optional sparks, connect the shading nodes to the
  group, and select it.
- `_create_group` adds two attributes: `slashTrailSettings` (the JSON) and
  `slashTrailShading` (a message multi). Every shading node is connected to
  the multi by explicit index, so `delete()` can find and remove exactly
  the nodes this trail created, and nothing else.
- `_create_mesh` makes a transform first and passes it as the parent to
  `MFnMesh.create`. When the parent is a transform, `MFnMesh.create` only
  adds a shape under it, so creating the transform ourselves controls the
  name. UVs are assigned with the same index list as the faces. Shadows
  are turned off and, if Arnold is loaded, `aiOpaque` is off so the
  opacity works in renders.
- `_create_trail_shader`: a `standardSurface` with no base or specular,
  emission at `glow`, and `thinWalled` on. Emission color comes from the V
  "core" ramp and the edge opacity from the V "edge" ramp; `look.py` picks
  their entries for the mode (white-hot at the tip for a blade, in the
  middle for a point trail). Opacity is
  `multiplyDivide(ageRamp, edgeRamp)`. The age ramp's `place2dTexture` has
  `wrapU` off, `coverageU` from `reveal.coverage`, and `translateFrameU`
  keyed from `reveal.keys` with linear tangents.
- `_create_sparks` / `_key_spark`: one streak mesh per spark, keyed linearly
  from birth to death in translate, scaled from 1 to 0, and with stepped
  visibility keys so it only exists while alive. The spark shader fades
  along the streak's U.
- `fit_to_motion(settings, start, end)` samples one point per frame over
  the given range (the window passes the playback range), runs
  `auto.suggest` and returns the fitted copy.
- `rebuild(group, settings=None)` deletes the group and calls `create`
  again under the same name. Without settings it reuses the stored ones
  (re-sampling changed animation); with settings (the window's values) it
  keeps the stored trail name. `read_settings`, `is_trail`, `list_trails` and
  `selected_trails` (which walks up from any selected child) support the UI.

### `look.py`

`edge_entries`, `core_entries` and `age_entries` return the ramp entries
the shader uses. Blade trails use `EDGE_GRADIENT` and a core that ends in
white at V = 1. Point trails use `CENTER_EDGE_GRADIENT` and a core that is
white in the middle (V = 0.5) and dim at both edges. Keeping the choice here
means the tests check it without Maya.

### `ui.py`

`SlashTrailDialog` is a `QDialog` with four group boxes (Source, Timing,
Look, Sparks), the action buttons and a status label.

- It never imports Maya directly. It talks to a `builder` (default
  `maya_build`) and a `scene` (default `MayaScene`, for selection and
  playback range). The tests inject fakes and run the real window
  offscreen.
- `settings()` and `set_settings()` convert between widgets and
  `TrailSettings`. The round trip is tested.
- The Source box has the object field, the point-trail fields (Width, Face,
  Camera) and a "Use blade (base + tip)" checkbox with the blade fields
  under it. `_update_mode_state` enables only what the current mode uses:
  the camera field only when facing the camera, axis and length only for a
  blade without a tip object, and inner edge only for blades.
- Errors from the builder (`ValueError`, `RuntimeError`) go to the status
  label in red instead of a stack trace.
- The window follows the Maya selection: `MayaScene.watch_selection` starts
  a `SelectionChanged` scriptJob (killed in `closeEvent`), and
  `on_selection_changed` loads a selected trail's stored values into the
  window. "Rebuild Selected" then rebuilds one selected trail with what the
  window shows, or several trails each from their stored values.
- Why: in real use, a user raised the trail length in the window and pressed
  Rebuild, but Rebuild only used the values stored on the trail, so nothing
  changed. A separate "Update" button was tried and was just as confusing.
  Making the window always show the selected trail's values means what you
  see is what Rebuild uses.
- `fit_to_motion()` asks the builder for fitted settings over the whole
  playback range and shows them, with a status line such as "Fitted to
  hand_ctl: frames 15-21, trail 3.5 frames". It runs from the "Fit to
  motion" button, when the object or tip is picked with "<< Selected", and
  when the window opens with something selected.
- `show()` parents the window to Maya's main window through `shiboken`,
  replaces an already open copy, and pre-fills the object from the
  selection (two selected objects switch on blade mode with a tip) and the
  range from the timeline.
- `PySide6` is tried first and `PySide2` is the fallback for Maya 2024.

### `install.py` and `install_slash_trail.py`

Installing without editing `PYTHONPATH` uses a **Maya module file**. Maya
reads every `.mod` file in the module path at startup (the user's
`Documents/maya/modules` is on it by default). A file like

```
+ slash_trail 1.0.0 D:/tools/maya-slash-trail
PYTHONPATH +:= python
```

declares a module rooted at that folder and adds its `python` subfolder to
`sys.path`. That is the standard way Maya tools are shipped.

- `module_text(root)` builds that text with forward slashes, which Maya
  accepts on every OS.
- `write_module_file(root, modules_dir)` checks that `root` really holds the
  package, creates the modules folder if needed, and overwrites an old
  file, so dragging again after moving the folder fixes the path.
- `add_to_session(root)` puts `python` on `sys.path` right away, so there is
  no restart.
- `add_shelf_button()` finds the current shelf through MEL's
  `$gShelfTopLevel` and adds a "Slash" button. A `docTag` marks the button
  so a second install does not add a duplicate. In batch or standalone
  sessions there are no shelves, so it returns `None`.
- `run(root)` does all of it and prints a short report.
- `install_slash_trail.py` sits at the repo root. When a `.py` file is dropped
  into the viewport, Maya runs it and calls `onMayaDroppedPythonFile`. The
  file finds its own folder through its code object (the same `__file__`
  trick as in rep-switch's plug-in), puts `python` on `sys.path` and calls
  `install.run`.
  Why the file has a tool-specific name: Maya imports a dropped file as a
  module named after the file (`importlib.import_module` in
  `maya/app/general/executeDroppedPythonFile.py`). Both repos first used
  `drag_into_maya.py`, so after one tool was installed, dropping the other
  repo's file reused the cached module and ran the first installer again.
  Each installer now has its own name and removes itself from `sys.modules`
  after running, so dropping it again after an update runs the new code.

I checked the module file for real: with only `MAYA_MODULE_PATH` pointing at
a folder holding the `.mod`, a fresh `mayapy` session imports `slash_trail`.

### Tests (`python/slash_trail/test/`)

- `conftest.py` creates the `QApplication` before any test module is
  collected. Under `mayapy`, `maya.standalone.initialize` would otherwise
  create a `QCoreApplication`, and building widgets on that crashes the
  interpreter.
- `test_vecmath.py`, `test_settings.py`, `test_ribbon.py`, `test_reveal.py`,
  `test_look.py`, `test_auto.py` and `test_sparks.py` cover the pure core
  (including the slow-cube case for `auto`): validation per
  mode, JSON round trip and the legacy `use_blade` default, camera-facing
  sides, mesh layout and UVs, reveal math, ramp entries per mode,
  deterministic sparks.
- `test_ui.py` drives the dialog with a fake builder and scene.
- `test_maya_build.py` animates a hilt locator turning 90 degrees with a
  tip locator 10 units out, and checks:
  - sampling does not move the current frame, and the positions are
    exact;
  - one-object (axis) mode matches two-object mode;
  - the mesh has the expected vertex, face and UV counts, and its last tip
    vertex is where the tip ends up;
  - the reveal keys are at `start` and `end + L`;
  - `colorAtPoint` on the age ramp matches `reveal.ramp_position` and
    `AGE_GRADIENT`, is 0 ahead of the blade and behind the tail, and is 0
    before the swing and after it drains;
  - sparks are created and keyed, rebuild keeps the name, and delete
    removes the group and every shading node;
  - a point trail on the tip locator is centred on it, has the right width,
    and its width is perpendicular to the line of sight from a camera
    (dot product 0);
  - facing an axis puts the width along that axis;
  - a built point trail has its edge ramp brightest in the middle;
  - fitting a blade crops the range to the swing and sizes from the blade;
  - fitting a slow 1-unit cube gives a trail that passes the short-trail
    check.
- `test_install.py` checks the module file text, writing and overwriting it,
  a wrong folder, and that the session path is added once.
  `test_maya_install.py` runs the real `install_slash_trail.py` entry point
  against a temporary modules folder, and checks that the shelf step is
  skipped cleanly without shelves.

## 4. Design decisions and trade-offs

- **Static mesh + animated texture window vs. per-frame geometry.** One mesh
  is cheap, scrubs instantly and is easy to rebuild. The cost: the ribbon's
  shape is fixed to the sampled swing, so
  changing the animation needs a Rebuild (the stored settings make that one
  click).
- **Sampling via `MDGContext`.** No timeline changes, sub-frame accuracy,
  and it picks up anything that drives the object.
- **Pure core, thin Maya layer.** All the math lives in pure modules with
  fast tests; the Maya modules only translate data into nodes.
- **Shading nodes tracked by message connections.** Delete and Rebuild
  never guess node names, and two trails never clean up each other's
  nodes.
- **Spark streak quads instead of nParticles.** They are deterministic,
  cheap, render the same in Arnold and the viewport, and need no solver
  cache.
- **API 2.0 for sampling and mesh creation, `maya.cmds` for nodes and keys.**
  This follows the repo style: API 2.0 where it matters for speed and data,
  cmds for scene setup.

## 5. Known limitations

- The blade position at the exact current frame sits on the edge of the
  texture frame, so the front column of the ribbon is transparent. The
  quad just behind it is fully lit, so in practice it is not visible.
- The trail lives in world space under its group. Moving the group moves the
  trail away from the blade; rebuild instead.
- A camera-facing point trail faces the camera it was built for. Seen from a
  very different camera it can look thin; rebuild it for that camera.
- Sparks fly in straight lines with no gravity or drag.
- The look is tuned for Arnold and Viewport 2.0 with `standardSurface`; other
  renderers need their own emission/opacity hookup.

## 6. Likely interview questions

1. **Why not create geometry per frame?** One static ribbon plus a moving
   texture window scrubs instantly, is one node to manage, and is how game
   engines draw weapon trails. The window math (`reveal.py`) is two linear
   keys.
2. **How do you sample positions without changing the frame?** Evaluate
   `worldMatrix[0]` with `MPlug.asMObject(MDGContext(MTime(t)))` and read
   the translation from the matrix.
3. **How does a blade without a tip object find the tip?** The rows of the
   world matrix are the object's axes in world space, so the tip is
   `translation + axisRow * length`.
4. **How does a point trail face the camera?** At each sample the width
   direction is `cross(tangent, view)`, perpendicular to both the motion and
   the line of sight, so the ribbon is seen flat-on. The camera is sampled
   at the same times, so a moving camera works too. When the cross product
   is zero, the previous side is reused to avoid flips.
5. **What does `wrapU = 0` do here?** Outside the coverage frame the texture
   returns its default color. The default is black, and black opacity is
   transparent, so everything outside the window disappears.
6. **Why multiply two ramps for opacity?** Age (U) controls the fade over
   time; edge (V) keeps the energy near the tip (or the middle for a point
   trail). Multiplying them fades the trail both along and across it.
7. **How do Rebuild and Delete know what to touch?** Settings are JSON on
   the group, and every shading node is message-connected to it.
8. **How did you test shading in a headless Maya?** `colorAtPoint` evaluates
   the ramp through its `place2dTexture`, so the test compares it with the
   pure `reveal.ramp_position` at several frames.
9. **Why is the UI testable without Maya?** It depends on a builder and a
   scene object, not on `maya.cmds`. The tests pass fakes and run Qt
   offscreen.
10. **What crashed when UI and Maya tests ran together, and how did you fix
   it?** `maya.standalone` creates a `QCoreApplication`, and Qt widgets need
   a `QApplication`. Creating the `QApplication` first in `conftest.py`
   makes Maya reuse it.
11. **How are sparks reproducible?** A seeded `random.Random`, stored in the
    settings.
12. **Why `MFnMesh.create` instead of `polyCreateFacet` or `cmds`?** It
    builds the whole mesh, including UVs, in one call from flat arrays,
    which is much faster for hundreds of faces.
13. **How does it pick defaults that make the first trail visible?** It
    samples the object once per frame, crops the range to where it moves,
    and sets the trail length so the visible part is about three object
    sizes long at the average speed (`auto.py`). Samples per frame scale
    with top speed so fast arcs stay smooth.
14. **How do users install it without touching PYTHONPATH?** A Maya
    module file in their modules folder, written by a drag-and-drop
    installer that also adds a shelf button. Studios can put the same
    `.mod` on a shared `MAYA_MODULE_PATH` or use the Rez package.
15. **How did old trails keep working after adding point trails?**
    `from_json` defaults `use_blade` to `True` when the key is missing,
    because every trail saved before the flag existed was a blade.
16. **What would you add next?** A viewport-only preview mode, curve-based
    smoothing for very fast swings with few samples, gravity on sparks, and
    an export to Alembic for game engines.
