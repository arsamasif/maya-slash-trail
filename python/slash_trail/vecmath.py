"""Small 3D vector helpers on plain tuples.

Just enough math for the ribbon and spark code, so the core stays free of
numpy and Maya and can run anywhere pytest runs.

"""

import math


def add(a, b):
    """Return a + b.

    Args:
        a (tuple): Vector.
        b (tuple): Vector.

    Returns:
        tuple: The sum.

    """
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    """Return a - b.

    Args:
        a (tuple): Vector.
        b (tuple): Vector.

    Returns:
        tuple: The difference.

    """
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, factor):
    """Return a scaled by a number.

    Args:
        a (tuple): Vector.
        factor (float): Scale factor.

    Returns:
        tuple: The scaled vector.

    """
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def lerp(a, b, t):
    """Linearly interpolate between two points.

    Args:
        a (tuple): Point at t=0.
        b (tuple): Point at t=1.
        t (float): Blend factor.

    Returns:
        tuple: The blended point.

    """
    return add(a, scale(sub(b, a), t))


def dot(a, b):
    """Return the dot product.

    Args:
        a (tuple): Vector.
        b (tuple): Vector.

    Returns:
        float: a . b

    """
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    """Return the cross product.

    Args:
        a (tuple): Vector.
        b (tuple): Vector.

    Returns:
        tuple: a x b

    """
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a):
    """Return the length of a vector.

    Args:
        a (tuple): Vector.

    Returns:
        float: Euclidean length.

    """
    return math.sqrt(dot(a, a))


def normalize(a, fallback=(0.0, 1.0, 0.0)):
    """Return a unit vector, or a fallback for a zero vector.

    Args:
        a (tuple): Vector.
        fallback (tuple): Returned when ``a`` has no length.

    Returns:
        tuple: Unit vector.

    """
    size = length(a)
    if size < 1e-9:
        return fallback
    return scale(a, 1.0 / size)
