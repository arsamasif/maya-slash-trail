"""Build the ribbon mesh that follows the blade through the swing.

Every sample time gives one column of two vertices: one on the blade tip
and one part way down the blade. Neighbouring columns are joined by quads.
U runs along time (0 at the first sample, 1 at the last), V across the
blade (0 at the inner edge, 1 at the tip), which is what the shader uses
to reveal and fade the trail.

"""

import dataclasses

from slash_trail import vecmath


@dataclasses.dataclass
class RibbonMesh:
    """Mesh data in the layout ``MFnMesh.create`` expects.

    Attributes:
        points (list): Vertex positions as (x, y, z) tuples.
        face_counts (list): Vertex count per face (always 4).
        face_connects (list): Vertex indices per face, flattened.
        us (list): U per UV, one UV per vertex.
        vs (list): V per UV.

    """

    points: list
    face_counts: list
    face_connects: list
    us: list
    vs: list

    @property
    def face_count(self):
        """int: Number of faces."""
        return len(self.face_counts)


def sample_times(start, end, substeps):
    """Return evenly spaced sample times from start to end.

    Args:
        start (float): First frame.
        end (float): Last frame, included.
        substeps (int): Samples per frame.

    Returns:
        list: Frame numbers as floats.

    Raises:
        ValueError: If the range is empty or substeps is below 1.

    """
    if end <= start:
        raise ValueError("End frame {0} is not after start frame {1}".format(end, start))
    if substeps < 1:
        raise ValueError("Substeps must be 1 or more, got {0}".format(substeps))
    count = int(round((end - start) * substeps))
    step = (end - start) / count
    return [start + index * step for index in range(count)] + [float(end)]


def blade_tips(base_points, base_axes, length):
    """Derive tip positions from base positions and a blade direction.

    Used when only one object drives the trail.

    Args:
        base_points (list): Base positions per sample.
        base_axes (list): World direction of the blade per sample.
        length (float): Blade length.

    Returns:
        list: Tip positions per sample.

    """
    return [
        vecmath.add(point, vecmath.scale(vecmath.normalize(axis), length))
        for point, axis in zip(base_points, base_axes)
    ]


def camera_sides(centers, eye_points):
    """Return width directions that keep a point trail facing a camera.

    The side is perpendicular to both the direction of travel and the line
    of sight, so the ribbon lies flat towards the camera. When the object
    stands still or moves straight at the camera, the previous side is
    reused so the ribbon does not flip.

    Args:
        centers (list): Object position per sample.
        eye_points (list): Camera position per sample.

    Returns:
        list: Unit side vectors per sample.

    """
    sides = []
    previous = (0.0, 1.0, 0.0)
    last = len(centers) - 1
    for index, (center, eye) in enumerate(zip(centers, eye_points)):
        ahead = centers[min(index + 1, last)]
        behind = centers[max(index - 1, 0)]
        tangent = vecmath.sub(ahead, behind)
        view = vecmath.sub(center, eye)
        side = vecmath.normalize(vecmath.cross(tangent, view), fallback=previous)
        sides.append(side)
        previous = side
    return sides


def point_edges(centers, sides, width):
    """Return the two ribbon edges of a trail centred on a moving point.

    Args:
        centers (list): Object position per sample.
        sides (list): Width direction per sample.
        width (float): Ribbon width.

    Returns:
        tuple: (first_edge, second_edge) point lists, usable as the base and
        tip of ``build`` with ``inner=0``.

    """
    first = []
    second = []
    for center, side in zip(centers, sides):
        half = vecmath.scale(vecmath.normalize(side), width * 0.5)
        first.append(vecmath.sub(center, half))
        second.append(vecmath.add(center, half))
    return first, second


def swept_distance(points, window):
    """Return the longest path covered within any run of samples.

    Used to warn when the visible part of a trail is so short that the
    object itself would hide it.

    Args:
        points (list): Positions per sample.
        window (int): Number of sample steps in the run.

    Returns:
        float: Longest path length over ``window`` consecutive steps.

    """
    steps = [vecmath.length(vecmath.sub(b, a)) for a, b in zip(points, points[1:])]
    window = max(1, min(window, len(steps)))
    best = current = sum(steps[:window])
    for index in range(window, len(steps)):
        current += steps[index] - steps[index - window]
        best = max(best, current)
    return best


def short_trail_warning(base_points, tip_points, inner, window):
    """Describe a trail too short to see past the object, or return "".

    Args:
        base_points (list): Blade base per sample.
        tip_points (list): Blade tip per sample.
        inner (float): Inner edge position along the blade.
        window (int): Samples covered by the visible trail.

    Returns:
        str: Warning text, empty when the trail is long enough.

    """
    swept = swept_distance(tip_points, window)
    blades = [vecmath.length(vecmath.sub(tip, base)) for base, tip in zip(base_points, tip_points)]
    width = max(blades) * (1.0 - inner) if blades else 0.0
    if swept >= width:
        return ""
    return (
        "The blade tip only travels {0:.2f} units within the trail length, less than the "
        "ribbon width of {1:.2f}, so the object may hide the trail. Use a longer trail "
        "or a faster swing.".format(swept, width)
    )


def build(base_points, tip_points, inner=0.35):
    """Build the ribbon between the blade and its inner edge.

    Args:
        base_points (list): Blade base position per sample.
        tip_points (list): Blade tip position per sample.
        inner (float): Where the inner edge sits along the blade,
            0 at the base and 1 at the tip.

    Returns:
        RibbonMesh: The mesh data.

    Raises:
        ValueError: If there are fewer than two samples or the lists differ.

    """
    if len(base_points) != len(tip_points):
        raise ValueError(
            "Got {0} base samples and {1} tip samples".format(len(base_points), len(tip_points))
        )
    if len(base_points) < 2:
        raise ValueError("A ribbon needs at least two samples")
    last = len(base_points) - 1
    points = []
    us = []
    vs = []
    for index, (base, tip) in enumerate(zip(base_points, tip_points)):
        u = index / last
        points.append(vecmath.lerp(base, tip, inner))
        points.append(tuple(tip))
        us.extend((u, u))
        vs.extend((0.0, 1.0))
    face_counts = []
    face_connects = []
    for index in range(last):
        inner_a = index * 2
        face_counts.append(4)
        face_connects.extend((inner_a, inner_a + 2, inner_a + 3, inner_a + 1))
    return RibbonMesh(points, face_counts, face_connects, us, vs)
