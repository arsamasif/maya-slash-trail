"""Ramp entries for the trail shader.

Picks the gradients for the two trail modes. A blade trail is brightest at
the blade tip (V = 1); a point trail is brightest along the object's path in
the middle of the ribbon (V = 0.5). Kept out of ``maya_build`` so the
choices are tested without Maya.

"""

from slash_trail import constants
from slash_trail import vecmath

WHITE = (1.0, 1.0, 1.0)


def edge_entries(settings):
    """Return the opacity ramp entries across the ribbon.

    Args:
        settings (TrailSettings): Uses ``use_blade``.

    Returns:
        list: (position, (r, g, b)) gray entries, V from 0 to 1.

    """
    gradient = constants.EDGE_GRADIENT if settings.use_blade else constants.CENTER_EDGE_GRADIENT
    return [(position, (value, value, value)) for position, value in gradient]


def core_entries(settings):
    """Return the emission ramp entries across the ribbon.

    The glow color is dimmer towards the edges and blends towards white by
    ``core_white`` where the trail is brightest.

    Args:
        settings (TrailSettings): Uses ``use_blade``, ``color`` and
            ``core_white``.

    Returns:
        list: (position, (r, g, b)) entries, V from 0 to 1.

    """
    color = settings.color
    hot = vecmath.lerp(color, WHITE, settings.core_white)
    if settings.use_blade:
        entries = [
            (position, vecmath.scale(color, value)) for position, value in constants.CORE_GRADIENT
        ]
        return entries + [(1.0, hot)]
    dim = vecmath.scale(color, constants.CORE_GRADIENT[0][1])
    return [(0.0, dim), (0.3, color), (0.5, hot), (0.7, color), (1.0, dim)]


def age_entries():
    """Return the opacity ramp entries along the trail, tail to head.

    Returns:
        list: (position, (r, g, b)) gray entries, U from 0 to 1.

    """
    return [(position, (value, value, value)) for position, value in constants.AGE_GRADIENT]
