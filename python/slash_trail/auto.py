"""Suggest trail settings from how an object moves.

Given the object's position per frame and its size, ``suggest`` picks a
frame range around the actual movement, a trail length that makes the
visible trail clearly longer than the object, enough samples per frame for
fast moves, and a width and spark settings in proportion. The goal is that
the first trail an animator creates is visible without tweaking.

"""

import dataclasses
import math

from slash_trail import constants
from slash_trail import vecmath

# Frames where the object moves slower than this fraction of its top speed
# count as standing still when cropping the frame range.
MOVING_FRACTION = 0.15

# The visible trail should be this many object sizes long.
TRAIL_SIZES = 3.0
MIN_TRAIL_FRAMES = 2.0
MAX_TRAIL_FRAMES = 24.0

# One sample step should cover at most this fraction of the object size.
STEP_SIZE_FRACTION = 0.2
MAX_SUBSTEPS = 16

WIDTH_SIZE_FRACTION = 0.75
SPARK_SPEED_FRACTION = 0.5
SPARK_LIFE_TRAILS = 1.5

# Used when the object has no size of its own (a locator, a joint).
PATH_SIZE_FRACTION = 0.05


@dataclasses.dataclass(frozen=True)
class Suggestion:
    """Suggested values for a trail.

    Attributes:
        start (float): First frame of the movement.
        end (float): Last frame of the movement.
        trail_frames (float): Trail length in frames.
        substeps (int): Samples per frame.
        width (float): Ribbon width for a point trail.
        spark_speed (float): Spark speed in units per frame.
        spark_life (float): Spark life in frames.
        size (float): Object size the suggestion was based on.

    """

    start: float
    end: float
    trail_frames: float
    substeps: int
    width: float
    spark_speed: float
    spark_life: float
    size: float


def suggest(times, positions, size):
    """Suggest settings for an object moving along a path.

    Args:
        times (list): Frames, at least two, increasing.
        positions (list): Position of the tracked point per frame (the tip
            for a blade).
        size (float): Object size, e.g. its bounding box diagonal or blade
            length. Zero or less falls back to a fraction of the path.

    Returns:
        Suggestion: The suggested values.

    Raises:
        ValueError: If there are too few samples or the object never moves.

    """
    if len(times) < 2 or len(times) != len(positions):
        raise ValueError("Need at least two frames of positions to fit a trail")
    steps = [vecmath.length(vecmath.sub(b, a)) for a, b in zip(positions, positions[1:])]
    speeds = [step / (t1 - t0) for step, t0, t1 in zip(steps, times, times[1:])]
    peak = max(speeds)
    if peak < 1e-6:
        raise ValueError("The object does not move between frames {0} and {1}".format(
            times[0], times[-1]
        ))

    moving = [index for index, speed in enumerate(speeds) if speed >= peak * MOVING_FRACTION]
    first, last = moving[0], moving[-1]
    start = times[first]
    end = times[last + 1]
    mean_speed = sum(steps[first:last + 1]) / (end - start)

    if size <= 0:
        size = sum(steps) * PATH_SIZE_FRACTION
    trail_frames = _clamp(TRAIL_SIZES * size / mean_speed, MIN_TRAIL_FRAMES, MAX_TRAIL_FRAMES)
    trail_frames = round(trail_frames * 2.0) / 2.0
    substeps = int(_clamp(math.ceil(peak / (size * STEP_SIZE_FRACTION)), 1, MAX_SUBSTEPS))
    while substeps > 1 and (end - start) * substeps + 1 > constants.MAX_SAMPLES:
        substeps -= 1

    return Suggestion(
        start=start,
        end=end,
        trail_frames=trail_frames,
        substeps=substeps,
        width=size * WIDTH_SIZE_FRACTION,
        spark_speed=mean_speed * SPARK_SPEED_FRACTION,
        spark_life=trail_frames * SPARK_LIFE_TRAILS,
        size=size,
    )


def apply(settings, suggestion):
    """Return a copy of settings with the suggested values filled in.

    Args:
        settings (TrailSettings): Settings to start from.
        suggestion (Suggestion): Values from ``suggest``.

    Returns:
        TrailSettings: New settings; the input is not changed.

    """
    return dataclasses.replace(
        settings,
        start=suggestion.start,
        end=suggestion.end,
        trail_frames=suggestion.trail_frames,
        substeps=suggestion.substeps,
        width=suggestion.width,
        spark_speed=suggestion.spark_speed,
        spark_life=suggestion.spark_life,
    )


def _clamp(value, low, high):
    return max(low, min(high, value))
