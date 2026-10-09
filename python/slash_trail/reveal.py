"""Timing of the trail reveal.

The ribbon covers the whole swing, so the shader hides everything except a
window that follows the blade. The window is a ``place2dTexture`` frame:
``coverageU`` is the window width and ``translateFrameU`` slides it along
the ribbon. With ``wrapU`` off, Maya returns the ramp's default color
(black, so transparent) outside the frame, and inside it the ramp runs from
the tail (0) to the blade (1).

For a ribbon spanning ``start``-``end`` and a trail of ``L`` frames, at the
current frame ``c`` the window is ``[(c - L - start) / D, (c - start) / D]``
with ``D = end - start``. It moves linearly with ``c``, so two linear keys,
one at ``start`` and one at ``end + L``, animate it exactly.

"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class RevealKey:
    """One key of the reveal animation.

    Attributes:
        frame (float): Frame of the key.
        translate_frame (float): ``translateFrameU`` value at that frame.

    """

    frame: float
    translate_frame: float


def coverage(start, end, trail_frames):
    """Return the window width in ribbon U.

    Args:
        start (float): First frame of the ribbon.
        end (float): Last frame of the ribbon.
        trail_frames (float): Trail length in frames.

    Returns:
        float: Value for ``coverageU``.

    """
    return trail_frames / (end - start)


def translate_frame(current, start, end, trail_frames):
    """Return where the window starts at a given frame.

    Args:
        current (float): Current frame.
        start (float): First frame of the ribbon.
        end (float): Last frame of the ribbon.
        trail_frames (float): Trail length in frames.

    Returns:
        float: Value for ``translateFrameU``.

    """
    return (current - trail_frames - start) / (end - start)


def keys(start, end, trail_frames):
    """Return the two linear keys that animate the window.

    The first key hides the trail (window ends at the ribbon start), the
    last one has drained it (window starts at the ribbon end).

    Args:
        start (float): First frame of the ribbon.
        end (float): Last frame of the ribbon.
        trail_frames (float): Trail length in frames.

    Returns:
        list: Two ``RevealKey`` objects.

    """
    last = end + trail_frames
    return [
        RevealKey(start, translate_frame(start, start, end, trail_frames)),
        RevealKey(last, translate_frame(last, start, end, trail_frames)),
    ]


def ramp_position(u, current, start, end, trail_frames):
    """Return where a ribbon U lands on the ramp at a given frame.

    Mirrors what ``place2dTexture`` computes, which makes the reveal easy to
    test without Maya.

    Args:
        u (float): Ribbon U, 0 at ``start`` and 1 at ``end``.
        current (float): Current frame.
        start (float): First frame of the ribbon.
        end (float): Last frame of the ribbon.
        trail_frames (float): Trail length in frames.

    Returns:
        float: Ramp position; outside 0-1 means hidden.

    """
    width = coverage(start, end, trail_frames)
    return (u - translate_frame(current, start, end, trail_frames)) / width
