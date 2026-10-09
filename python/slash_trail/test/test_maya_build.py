"""Maya tests for sampling and building trails; run with ``mayapy -m pytest``.

Animates a blade (a hilt locator with a tip locator parented under it)
through a quarter turn, builds trails from it and checks the mesh, the
reveal keys and the ramp output at a few frames. Skipped when Maya is not
importable.

"""

import pytest

pytest.importorskip("maya.standalone")

import maya.standalone  # noqa: E402

maya.standalone.initialize(name="python")

from maya import cmds  # noqa: E402

from slash_trail import constants  # noqa: E402
from slash_trail import maya_build  # noqa: E402
from slash_trail import maya_sample  # noqa: E402
from slash_trail import reveal  # noqa: E402
from slash_trail import ribbon  # noqa: E402
from slash_trail import settings  # noqa: E402

START = 1.0
END = 11.0
BLADE = 10.0


@pytest.fixture
def blade():
    """Return (hilt, tip) locators; the hilt turns 90 degrees around Y."""
    cmds.file(new=True, force=True)
    hilt = cmds.spaceLocator(name="hilt")[0]
    tip = cmds.spaceLocator(name="tip")[0]
    tip = cmds.parent(tip, hilt)[0]
    cmds.setAttr(tip + ".translateX", BLADE)
    for frame, angle in ((START, 0.0), (END, 90.0)):
        cmds.setKeyframe(
            hilt,
            attribute="rotateY",
            time=frame,
            value=angle,
            inTangentType="linear",
            outTangentType="linear",
        )
    cmds.currentTime(START)
    return cmds.ls(hilt, long=True)[0], cmds.ls(tip, long=True)[0]


def _age_gradient(position):
    points = constants.AGE_GRADIENT
    for (left, low), (right, high) in zip(points, points[1:]):
        if left <= position <= right:
            return low + (high - low) * (position - left) / (right - left)
    raise ValueError("Position {0} is outside the gradient".format(position))


def _settings(hilt, tip="", **overrides):
    values = {
        "base": hilt,
        "use_blade": True,
        "tip": tip,
        "axis": "x",
        "length": BLADE,
        "start": START,
        "end": END,
    }
    values.update(overrides)
    return settings.TrailSettings(**values)


def _point_settings(node, **overrides):
    values = {"base": node, "width": 2.0, "start": START, "end": END}
    values.update(overrides)
    return settings.TrailSettings(**values)


def _top_camera():
    camera = cmds.camera(name="topCam")[0]
    cmds.setAttr(camera + ".translateY", 50)
    cmds.setAttr(camera + ".rotateX", -90)
    return camera


def test_point_trail_centres_on_the_object_and_faces_the_camera(blade):
    _, tip = blade
    camera = _top_camera()
    times = [2.0, 6.0, 9.0]
    first, second = maya_sample.sample(_point_settings(tip, camera=camera), times)
    for time, a, b in zip(times, first, second):
        center = cmds.getAttr(tip + ".worldMatrix[0]", time=time)[12:15]
        middle = [(x + y) / 2 for x, y in zip(a, b)]
        assert middle == pytest.approx(center, abs=1e-6)
        assert sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 == pytest.approx(2.0)
        # The width runs across the line of sight, so the ribbon faces the
        # camera instead of being seen edge-on.
        view = [c - e for c, e in zip(center, (0.0, 50.0, 0.0))]
        across = [y - x for x, y in zip(a, b)]
        assert sum(v * w for v, w in zip(view, across)) == pytest.approx(0.0, abs=1e-6)


def test_point_trail_can_follow_an_object_axis(blade):
    _, tip = blade
    first, second = maya_sample.sample(_point_settings(tip, facing="y"), [3.0, 8.0])
    for a, b in zip(first, second):
        assert b[1] - a[1] == pytest.approx(2.0)
        assert (a[0], a[2]) == pytest.approx((b[0], b[2]))


def test_point_trail_builds_a_centred_ribbon(blade):
    _, tip = blade
    group = maya_build.create(_point_settings(tip, camera=_top_camera(), substeps=2))
    mesh = group + "|trailMesh"
    assert cmds.polyEvaluate(mesh, vertex=True) == 2 * 21
    shading = cmds.listConnections(group + ".slashTrailShading")
    edge_ramp = [node for node in cmds.ls(shading, type="ramp") if "Edge" in node][0]
    assert cmds.colorAtPoint(edge_ramp, u=0.5, v=0.5)[0] == pytest.approx(1.0)
    assert cmds.colorAtPoint(edge_ramp, u=0.5, v=0.02)[0] < 0.1
    assert maya_build.read_settings(group).use_blade is False


def test_sampling_does_not_move_the_timeline(blade):
    hilt, tip = blade
    base_points, tip_points = maya_sample.sample(_settings(hilt, tip), [START, 6.0, END])
    assert base_points[1] == pytest.approx((0.0, 0.0, 0.0))
    assert tip_points[0] == pytest.approx((BLADE, 0.0, 0.0), abs=1e-6)
    assert tip_points[2] == pytest.approx((0.0, 0.0, -BLADE), abs=1e-6)
    assert cmds.currentTime(query=True) == START


def test_axis_mode_matches_tip_mode(blade):
    hilt, tip = blade
    times = [START, 4.5, END]
    _, with_tip = maya_sample.sample(_settings(hilt, tip), times)
    _, with_axis = maya_sample.sample(_settings(hilt), times)
    for a, b in zip(with_tip, with_axis):
        assert a == pytest.approx(b, abs=1e-6)


def test_fit_to_motion_crops_to_the_swing_and_sizes_from_the_blade(blade):
    hilt, tip = blade
    fitted = maya_build.fit_to_motion(_settings(hilt, tip), 1.0, 30.0)
    assert (fitted.start, fitted.end) == (START, END)
    assert fitted.width == pytest.approx(BLADE * 0.75)
    fitted.validate()


def test_fit_to_motion_makes_a_slow_cube_visible():
    # A 1-unit cube sliding 10 units over 119 frames hid its default trail.
    cmds.file(new=True, force=True)
    cube = cmds.polyCube(name="slowCube")[0]
    cmds.setKeyframe(cube, attribute="translateX", time=1, value=0)
    cmds.setKeyframe(cube, attribute="translateX", time=119, value=10)
    fitted = maya_build.fit_to_motion(_point_settings(cube), 1.0, 120.0)
    times = ribbon.sample_times(fitted.start, fitted.end, fitted.substeps)
    first, second = maya_sample.sample(fitted, times)
    window = int(round(fitted.trail_frames * fitted.substeps))
    assert ribbon.short_trail_warning(first, second, 0.0, window) == ""


def test_missing_object_is_a_value_error(blade):
    with pytest.raises(ValueError, match="No object named"):
        maya_sample.sample(_settings("nope"), [START])


def test_create_builds_mesh_shader_and_keys(blade):
    hilt, tip = blade
    group = maya_build.create(_settings(hilt, tip, substeps=2, trail_frames=4))

    assert maya_build.list_trails() == [group]
    mesh = cmds.listRelatives(group, children=True, fullPath=True)[0]
    assert cmds.polyEvaluate(mesh, vertex=True) == 2 * 21
    assert cmds.polyEvaluate(mesh, face=True) == 20
    assert cmds.polyEvaluate(mesh, uvcoord=True) == 2 * 21

    tip_at_end = cmds.pointPosition(mesh + ".vtx[41]", world=True)
    assert tip_at_end == pytest.approx([0.0, 0.0, -BLADE], abs=1e-4)

    place = [node for node in cmds.listConnections(group + ".slashTrailShading") if "Age" in node]
    place = cmds.ls(place, type="place2dTexture")[0]
    assert cmds.keyframe(place + ".translateFrameU", query=True) == [START, END + 4]


def test_ramp_reveals_a_window_behind_the_blade(blade):
    hilt, tip = blade
    group = maya_build.create(_settings(hilt, tip, trail_frames=4))
    shading = cmds.listConnections(group + ".slashTrailShading")
    age_ramp = [node for node in cmds.ls(shading, type="ramp") if "Age" in node][0]

    def opacity(u, frame):
        cmds.currentTime(frame)
        return cmds.colorAtPoint(age_ramp, u=u, v=0.5)[0]

    span = END - START
    # Inside the window Maya must return the age gradient at the position
    # reveal.ramp_position predicts. The blade itself sits on the frame
    # edge, so the check stops just behind it.
    for frame in (4.0, 5.0, 6.0, 6.9):
        u = (frame - START) / span
        position = reveal.ramp_position(u, 7.0, START, END, 4)
        assert opacity(u, 7.0) == pytest.approx(_age_gradient(position), abs=0.01)
    assert opacity((8.0 - START) / span, 7.0) == pytest.approx(0.0)
    assert opacity((2.0 - START) / span, 7.0) == pytest.approx(0.0)
    assert opacity(0.5, START - 1.0) == pytest.approx(0.0)
    assert opacity(0.5, END + 10.0) == pytest.approx(0.0)


def test_sparks_rebuild_and_delete(blade):
    hilt, tip = blade
    group = maya_build.create(_settings(hilt, tip, sparks=True, spark_count=5, name="hero"))
    assert group == "|hero_slashTrail"
    spark_meshes = cmds.listRelatives(group + "|sparks", children=True)
    assert len(spark_meshes) == 5
    assert cmds.keyframe(group + "|sparks|spark1.translateX", query=True, keyframeCount=True) == 2

    cmds.select(group + "|trailMesh")
    assert maya_build.selected_trails() == [group]
    stored = maya_build.read_settings(group)
    assert stored.spark_count == 5

    rebuilt = maya_build.rebuild(group)
    assert rebuilt == "|hero_slashTrail"
    shading = cmds.listConnections(rebuilt + ".slashTrailShading")
    maya_build.delete(rebuilt)
    assert maya_build.list_trails() == []
    assert not cmds.ls(shading)


def test_rebuild_with_new_settings_keeps_the_name(blade):
    hilt, tip = blade
    group = maya_build.create(_settings(hilt, tip, name="hero", trail_frames=3))
    longer = _settings(hilt, tip, trail_frames=8)
    updated = maya_build.rebuild(group, longer)
    assert updated == "|hero_slashTrail"
    assert maya_build.read_settings(updated).trail_frames == 8
    assert maya_build.read_settings(updated).name == "hero"
    assert len(maya_build.list_trails()) == 1
