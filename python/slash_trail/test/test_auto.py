"""Tests for slash_trail.auto."""

import pytest

from slash_trail import auto
from slash_trail import constants
from slash_trail import settings

FRAMES = [float(frame) for frame in range(1, 31)]


def _path(speed_by_frame):
    positions = [(0.0, 0.0, 0.0)]
    for frame in FRAMES[1:]:
        x = positions[-1][0] + speed_by_frame(frame)
        positions.append((x, 0.0, 0.0))
    return positions


def test_range_is_cropped_to_the_movement():
    def speed(frame):
        return 2.0 if 11 <= frame <= 20 else 0.0

    result = auto.suggest(FRAMES, _path(speed), size=1.0)
    assert (result.start, result.end) == (10.0, 20.0)


def test_slow_object_gets_a_long_visible_trail():
    # The cube from a real test: 1 unit, sliding about 0.085 units a frame.
    result = auto.suggest(FRAMES, _path(lambda frame: 0.085), size=1.0)
    assert result.trail_frames == auto.MAX_TRAIL_FRAMES
    assert result.trail_frames * 0.085 > 1.0 * constants.DEFAULT_INNER


def test_fast_object_gets_a_short_trail_and_more_samples():
    slow = auto.suggest(FRAMES, _path(lambda frame: 1.0), size=2.0)
    fast = auto.suggest(FRAMES, _path(lambda frame: 4.0), size=2.0)
    assert fast.trail_frames < slow.trail_frames
    assert fast.trail_frames * 4.0 >= auto.TRAIL_SIZES * 2.0 - 2.0
    assert fast.substeps > slow.substeps
    assert fast.substeps <= auto.MAX_SUBSTEPS


def test_trail_frames_snap_to_half_frames():
    result = auto.suggest(FRAMES, _path(lambda frame: 0.7), size=1.0)
    assert result.trail_frames * 2 == int(result.trail_frames * 2)


def test_width_and_sparks_scale_with_the_object():
    small = auto.suggest(FRAMES, _path(lambda frame: 1.0), size=1.0)
    big = auto.suggest(FRAMES, _path(lambda frame: 1.0), size=4.0)
    assert big.width == pytest.approx(4 * small.width)
    assert small.spark_speed == pytest.approx(0.5)
    assert small.spark_life == pytest.approx(small.trail_frames * auto.SPARK_LIFE_TRAILS)


def test_objects_without_size_use_the_path():
    result = auto.suggest(FRAMES, _path(lambda frame: 1.0), size=0.0)
    assert result.size == pytest.approx(29 * auto.PATH_SIZE_FRACTION)


def test_still_object_is_an_error():
    with pytest.raises(ValueError, match="does not move"):
        auto.suggest(FRAMES, [(1.0, 2.0, 3.0)] * len(FRAMES), size=1.0)
    with pytest.raises(ValueError, match="two frames"):
        auto.suggest([1.0], [(0.0, 0.0, 0.0)], size=1.0)


def test_apply_keeps_everything_else():
    original = settings.TrailSettings(base="ball", color=(1.0, 0.0, 0.0), glow=7.0)
    suggestion = auto.suggest(FRAMES, _path(lambda frame: 1.0), size=2.0)
    fitted = auto.apply(original, suggestion)
    assert (fitted.base, fitted.color, fitted.glow) == ("ball", (1.0, 0.0, 0.0), 7.0)
    assert fitted.trail_frames == suggestion.trail_frames
    assert original.trail_frames == constants.DEFAULT_TRAIL_FRAMES
    fitted.validate()
