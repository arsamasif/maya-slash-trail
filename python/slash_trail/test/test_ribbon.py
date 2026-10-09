"""Tests for slash_trail.ribbon."""

import pytest

from slash_trail import ribbon


def test_sample_times_cover_range():
    times = ribbon.sample_times(1, 3, 4)
    assert len(times) == 9
    assert times[0] == 1
    assert times[-1] == 3
    assert times[1] == pytest.approx(1.25)


def test_sample_times_rejects_bad_input():
    with pytest.raises(ValueError, match="not after"):
        ribbon.sample_times(5, 5, 2)
    with pytest.raises(ValueError, match="Substeps"):
        ribbon.sample_times(1, 5, 0)


def test_build_layout():
    base = [(0, 0, 0), (0, 0, 0), (0, 0, 0)]
    tips = [(10, 0, 0), (0, 10, 0), (-10, 0, 0)]
    mesh = ribbon.build(base, tips, inner=0.5)

    assert len(mesh.points) == 6
    assert mesh.face_count == 2
    assert mesh.face_connects == [0, 2, 3, 1, 2, 4, 5, 3]
    assert mesh.points[0] == (5, 0, 0)
    assert mesh.points[1] == (10, 0, 0)
    assert mesh.us == [0, 0, 0.5, 0.5, 1, 1]
    assert mesh.vs == [0, 1, 0, 1, 0, 1]


def test_build_rejects_bad_input():
    with pytest.raises(ValueError, match="at least two"):
        ribbon.build([(0, 0, 0)], [(1, 0, 0)])
    with pytest.raises(ValueError, match="base samples"):
        ribbon.build([(0, 0, 0)] * 2, [(1, 0, 0)] * 3)


def test_swept_distance_finds_fastest_run():
    points = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (7, 0, 0), (12, 0, 0), (12, 1, 0)]
    assert ribbon.swept_distance(points, 2) == 10
    assert ribbon.swept_distance(points, 1) == 5
    assert ribbon.swept_distance(points, 99) == 13
    assert ribbon.swept_distance([(0, 0, 0)], 3) == 0


def test_short_trail_warning():
    base = [(float(index), 0.0, 0.0) for index in range(5)]
    slow_tips = [(float(index), 10.0, 0.0) for index in range(5)]
    assert "only travels 2.00" in ribbon.short_trail_warning(base, slow_tips, 0.0, 2)
    assert ribbon.short_trail_warning(base, slow_tips, 0.9, 2) == ""


def test_camera_sides_face_the_camera():
    centers = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    eyes = [(1.0, 0.0, 10.0)] * 3
    sides = ribbon.camera_sides(centers, eyes)
    for side in sides:
        assert side == pytest.approx((0.0, 1.0, 0.0)) or side == pytest.approx((0.0, -1.0, 0.0))
    assert sides[0] == sides[1] == sides[2]


def test_camera_sides_keep_previous_side_when_still():
    centers = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
    eyes = [(5.0, 0.0, 0.0)] * 4
    sides = ribbon.camera_sides(centers, eyes)
    assert sides[3] == sides[2]


def test_point_edges_are_centred():
    first, second = ribbon.point_edges([(0, 0, 0), (5, 0, 0)], [(0, 2, 0), (0, 1, 0)], 4.0)
    assert first == [(0, -2, 0), (5, -2, 0)]
    assert second == [(0, 2, 0), (5, 2, 0)]


def test_blade_tips_follow_axis():
    tips = ribbon.blade_tips([(1, 1, 1), (0, 0, 0)], [(0, 2, 0), (0, 0, -1)], 5)
    assert tips == [(1, 6, 1), (0, 0, -5)]
