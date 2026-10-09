"""Read world positions of the trail drivers from Maya.

Positions are evaluated with an ``MDGContext`` at each sample time, so the
current frame never changes and sub-frame samples come straight from the
animation curves (or constraints, IK, anything that drives the object).

Both trail modes return the two ribbon edges per sample: a blade trail
gives the blade base and tip, a point trail gives the two sides of a
ribbon centred on the object's pivot.

"""

import maya.api.OpenMaya as om

from slash_trail import constants
from slash_trail import ribbon

_AXIS_ROWS = {"x": 0, "y": 1, "z": 2}


def sample(settings, times):
    """Sample both ribbon edges for every time.

    Args:
        settings (TrailSettings): Uses ``base`` plus the blade fields
            (``tip``, ``axis``, ``length``) or the point fields (``width``,
            ``facing``, ``camera``) depending on ``use_blade``.
        times (list): Frames to sample.

    Returns:
        tuple: (first_edge, second_edge), each a list of (x, y, z). For a
        blade these are the base and the tip.

    Raises:
        ValueError: If a driver object or the camera does not exist.

    """
    if settings.use_blade:
        return _sample_blade(settings, times)
    return _sample_point(settings, times)


def motion(settings, times):
    """Sample the point that leads the trail and measure the object.

    For a blade the tip leads and the size is the longest blade length;
    for a point trail the pivot leads and the size is the diagonal of the
    object's world bounding box (zero for objects without geometry).

    Args:
        settings (TrailSettings): Uses ``base`` and, for a blade, the
            blade fields.
        times (list): Frames to sample.

    Returns:
        tuple: (positions, size).

    Raises:
        ValueError: If a driver object does not exist.

    """
    if settings.use_blade:
        bases, tips = _sample_blade(settings, times)
        size = max(_distance(base, tip) for base, tip in zip(bases, tips))
        return tips, size
    plug = _world_matrix_plug(settings.base)
    positions = [_translation(_matrix_at(plug, _context(time))) for time in times]
    return positions, _bounding_size(settings.base)


def _bounding_size(name):
    from maya import cmds

    box = cmds.exactWorldBoundingBox(name)
    return _distance(box[:3], box[3:])


def _distance(a, b):
    return sum((y - x) ** 2 for x, y in zip(a, b)) ** 0.5


def _sample_blade(settings, times):
    base_plug = _world_matrix_plug(settings.base)
    tip_plug = _world_matrix_plug(settings.tip) if settings.tip else None
    base_points = []
    tip_points = []
    for time in times:
        context = _context(time)
        base_matrix = _matrix_at(base_plug, context)
        base_points.append(_translation(base_matrix))
        if tip_plug is not None:
            tip_points.append(_translation(_matrix_at(tip_plug, context)))
        else:
            tip_points.append(_point_along_axis(base_matrix, settings.axis, settings.length))
    return base_points, tip_points


def _sample_point(settings, times):
    plug = _world_matrix_plug(settings.base)
    use_camera = settings.facing == constants.CAMERA_FACING
    camera_plug = _world_matrix_plug(settings.camera) if use_camera else None
    centers = []
    hints = []
    for time in times:
        context = _context(time)
        matrix = _matrix_at(plug, context)
        centers.append(_translation(matrix))
        if use_camera:
            hints.append(_translation(_matrix_at(camera_plug, context)))
        else:
            hints.append(_axis(matrix, settings.facing))
    sides = ribbon.camera_sides(centers, hints) if use_camera else hints
    return ribbon.point_edges(centers, sides, settings.width)


def _world_matrix_plug(name):
    selection = om.MSelectionList()
    try:
        selection.add(name)
    except RuntimeError:
        raise ValueError("No object named '{0}'".format(name)) from None
    node = selection.getDependNode(0)
    fn_node = om.MFnDependencyNode(node)
    if not fn_node.hasAttribute("worldMatrix"):
        raise ValueError("'{0}' has no world matrix, pick a transform".format(name))
    return fn_node.findPlug("worldMatrix", False).elementByLogicalIndex(0)


def _context(time):
    return om.MDGContext(om.MTime(time, om.MTime.uiUnit()))


def _matrix_at(plug, context):
    return om.MFnMatrixData(plug.asMObject(context)).matrix()


def _translation(matrix):
    return (matrix[12], matrix[13], matrix[14])


def _axis(matrix, axis):
    # The rows of a Maya world matrix are the object's axes in world space.
    row = _AXIS_ROWS[axis.lstrip("-")] * 4
    sign = -1.0 if axis.startswith("-") else 1.0
    return (matrix[row] * sign, matrix[row + 1] * sign, matrix[row + 2] * sign)


def _point_along_axis(matrix, axis, length):
    # The axis rows are already scaled, so a local point (0, length, 0) is
    # origin + row * length.
    direction = _axis(matrix, axis)
    return (
        matrix[12] + direction[0] * length,
        matrix[13] + direction[1] * length,
        matrix[14] + direction[2] * length,
    )
