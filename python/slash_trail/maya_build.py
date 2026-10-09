"""Create, rebuild and delete slash trails in a Maya scene.

A trail is a transform named ``<name>_slashTrail`` holding:

- the ribbon mesh built by ``ribbon.build`` from the two sampled edges
  (blade base and tip, or the two sides of a point trail);
- a ``standardSurface`` shader whose opacity is an age ramp (keyed through
  its ``place2dTexture`` frame, see ``reveal``) times an edge ramp, and
  whose emission goes from the glow color to white at the blade tip, or
  along the middle of a point trail;
- optional spark streaks with their own keys.

The settings are stored as JSON on the group, and the shading nodes are
connected to it, so Rebuild and Delete only need the group.

"""

import dataclasses

import maya.api.OpenMaya as om
from maya import cmds

from slash_trail import auto
from slash_trail import constants
from slash_trail import look
from slash_trail import maya_sample
from slash_trail import reveal
from slash_trail import ribbon
from slash_trail import settings as settings_module
from slash_trail import sparks
from slash_trail import vecmath

SHADING_ATTR = "slashTrailShading"
U_RAMP = 1
V_RAMP = 0


def create(settings):
    """Build a trail from settings.

    Args:
        settings (TrailSettings): What to build.

    Returns:
        str: Long name of the trail group.

    Raises:
        ValueError: If the settings are invalid or a driver is missing.

    """
    settings.validate()
    times = ribbon.sample_times(settings.start, settings.end, settings.substeps)
    base_points, tip_points = maya_sample.sample(settings, times)
    inner = settings.inner if settings.use_blade else 0.0
    window = int(round(settings.trail_frames * settings.substeps))
    warning = ribbon.short_trail_warning(base_points, tip_points, inner, window)
    if warning:
        om.MGlobal.displayWarning("Slash trail: " + warning)

    group = _create_group(settings)
    shading = []
    mesh = _create_mesh(ribbon.build(base_points, tip_points, inner), group, "trailMesh")
    trail_sg, trail_nodes = _create_trail_shader(settings)
    cmds.sets(mesh, edit=True, forceElement=trail_sg)
    shading.extend(trail_nodes)

    if settings.sparks:
        spark_list = sparks.generate(
            times,
            base_points,
            tip_points,
            settings.spark_count,
            settings.spark_speed,
            settings.spark_life,
            settings.seed,
        )
        spark_sg, spark_nodes = _create_spark_shader(settings)
        shading.extend(spark_nodes)
        _create_sparks(spark_list, group, spark_sg)

    _connect_shading(group, shading)
    cmds.select(group)
    return group


def fit_to_motion(settings, start, end):
    """Suggest timing, width and spark values from how the object moves.

    Samples the leading point once per frame between start and end and
    lets ``auto.suggest`` crop the range and size the trail.

    Args:
        settings (TrailSettings): Settings with the object (and blade)
            filled in.
        start (float): First frame to look at, usually the playback start.
        end (float): Last frame to look at.

    Returns:
        TrailSettings: A copy with the suggested values.

    Raises:
        ValueError: If the object is missing or does not move.

    """
    if not settings.base:
        raise ValueError("Pick an object to drive the trail")
    times = ribbon.sample_times(start, end, 1)
    positions, size = maya_sample.motion(settings, times)
    return auto.apply(settings, auto.suggest(times, positions, size))


def rebuild(group, settings=None):
    """Delete a trail and build it again under the same name.

    Args:
        group (str): Trail group.
        settings (TrailSettings): New settings to build with, e.g. from the
            window. None reuses the stored settings, which re-samples the
            current animation.

    Returns:
        str: Long name of the new trail group.

    """
    stored = read_settings(group)
    if settings is None:
        settings = stored
    else:
        settings = dataclasses.replace(settings, name=stored.trail_name)
    settings.validate()
    delete(group)
    return create(settings)


def delete(group):
    """Delete a trail group and the shading nodes it created.

    Args:
        group (str): Trail group.

    """
    shading = cmds.listConnections(group + "." + SHADING_ATTR, source=True) or []
    cmds.delete([group] + [node for node in shading if cmds.objExists(node)])


def read_settings(group):
    """Return the settings a trail was built with.

    Args:
        group (str): Trail group.

    Returns:
        TrailSettings: The stored settings.

    Raises:
        ValueError: If the node is not a trail group.

    """
    if not is_trail(group):
        raise ValueError("'{0}' is not a slash trail".format(group))
    text = cmds.getAttr(group + "." + constants.SETTINGS_ATTR)
    return settings_module.TrailSettings.from_json(text)


def is_trail(node):
    """Tell if a node is a trail group.

    Args:
        node (str): Node name.

    Returns:
        bool: True when the node carries trail settings.

    """
    return cmds.objExists(node) and cmds.attributeQuery(
        constants.SETTINGS_ATTR, node=node, exists=True
    )


def list_trails():
    """Return every trail group in the scene.

    Returns:
        list: Long names.

    """
    return [node for node in cmds.ls(type="transform", long=True) or [] if is_trail(node)]


def selected_trails():
    """Return trail groups that are selected or contain the selection.

    Returns:
        list: Long names without duplicates.

    """
    found = []
    for path in cmds.ls(selection=True, long=True) or []:
        parts = path.split("|")
        for depth in range(len(parts), 1, -1):
            candidate = "|".join(parts[:depth])
            if is_trail(candidate):
                if candidate not in found:
                    found.append(candidate)
                break
    return found


def _create_group(settings):
    name = _unique_name(settings.trail_name + constants.GROUP_SUFFIX)
    group = cmds.ls(cmds.createNode("transform", name=name), long=True)[0]
    cmds.addAttr(group, longName=constants.SETTINGS_ATTR, dataType="string")
    cmds.setAttr(group + "." + constants.SETTINGS_ATTR, settings.to_json(), type="string")
    cmds.addAttr(group, longName=SHADING_ATTR, attributeType="message", multi=True)
    return group


def _create_mesh(mesh_data, parent, name):
    # With a transform as parent, MFnMesh.create adds just the shape under
    # it, so the transform is made first to control its name.
    path = cmds.ls(cmds.createNode("transform", name=name, parent=parent), long=True)[0]
    selection = om.MSelectionList()
    selection.add(path)
    fn_mesh = om.MFnMesh()
    shape_object = fn_mesh.create(
        [om.MPoint(*point) for point in mesh_data.points],
        mesh_data.face_counts,
        mesh_data.face_connects,
        mesh_data.us,
        mesh_data.vs,
        parent=selection.getDependNode(0),
    )
    fn_mesh.assignUVs(mesh_data.face_counts, mesh_data.face_connects)
    shape = om.MDagPath.getAPathTo(shape_object).fullPathName()
    shape = cmds.rename(shape, name.rsplit("|", 1)[-1] + "Shape")
    shape = cmds.listRelatives(path, shapes=True, fullPath=True)[0]
    cmds.setAttr(shape + ".castsShadows", 0)
    cmds.setAttr(shape + ".receiveShadows", 0)
    if cmds.attributeQuery("aiOpaque", node=shape, exists=True):
        cmds.setAttr(shape + ".aiOpaque", 0)
    return path


def _create_trail_shader(settings):
    prefix = settings.trail_name + "_trail"
    surface, sg = _emissive_surface(prefix, settings.glow)

    core_ramp, core_place = _ramp(prefix + "Core", V_RAMP, look.core_entries(settings))
    cmds.connectAttr(core_ramp + ".outColor", surface + ".emissionColor")

    age_ramp, age_place = _ramp(prefix + "Age", U_RAMP, look.age_entries())
    cmds.setAttr(age_place + ".wrapU", 0)
    cmds.setAttr(age_place + ".coverageU", reveal.coverage(settings.start, settings.end, settings.trail_frames))
    for key in reveal.keys(settings.start, settings.end, settings.trail_frames):
        cmds.setKeyframe(
            age_place,
            attribute="translateFrameU",
            time=key.frame,
            value=key.translate_frame,
            inTangentType="linear",
            outTangentType="linear",
        )

    edge_ramp, edge_place = _ramp(prefix + "Edge", V_RAMP, look.edge_entries(settings))
    multiply = cmds.shadingNode("multiplyDivide", asUtility=True, name=prefix + "Opacity")
    cmds.connectAttr(age_ramp + ".outColor", multiply + ".input1")
    cmds.connectAttr(edge_ramp + ".outColor", multiply + ".input2")
    cmds.connectAttr(multiply + ".output", surface + ".opacity")

    nodes = [surface, sg, core_ramp, core_place, age_ramp, age_place, edge_ramp, edge_place, multiply]
    return sg, nodes


def _create_spark_shader(settings):
    prefix = settings.trail_name + "_spark"
    surface, sg = _emissive_surface(prefix, settings.glow)
    hot = vecmath.lerp(settings.color, (1.0, 1.0, 1.0), settings.core_white)
    cmds.setAttr(surface + ".emissionColor", *hot, type="double3")
    fade, place = _ramp(prefix + "Fade", U_RAMP, [(0.0, (0.0, 0.0, 0.0)), (1.0, (1.0, 1.0, 1.0))])
    cmds.connectAttr(fade + ".outColor", surface + ".opacity")
    return sg, [surface, sg, fade, place]


def _create_sparks(spark_list, group, shading_group):
    spark_group = cmds.createNode("transform", name=constants.SPARKS_NAME, parent=group)
    spark_group = cmds.ls(spark_group, long=True)[0]
    for index, spark in enumerate(spark_list):
        streak_length = vecmath.length(spark.velocity) * constants.SPARK_STREAK_FRAMES
        quad = sparks.streak(spark, streak_length, streak_length * constants.SPARK_WIDTH_RATIO)
        mesh = _create_mesh(quad, spark_group, "spark{0}".format(index + 1))
        cmds.sets(mesh, edit=True, forceElement=shading_group)
        _key_spark(mesh, spark)


def _key_spark(mesh, spark):
    for frame, position, size in (
        (spark.birth, spark.position, 1.0),
        (spark.death, spark.end_position, 0.0),
    ):
        for axis, value in zip("xyz", position):
            cmds.setKeyframe(
                mesh,
                attribute="translate" + axis.upper(),
                time=frame,
                value=value,
                inTangentType="linear",
                outTangentType="linear",
            )
        for axis in "XYZ":
            cmds.setKeyframe(mesh, attribute="scale" + axis, time=frame, value=size)
    cmds.setKeyframe(mesh, attribute="visibility", time=spark.birth - 0.01, value=0)
    cmds.setKeyframe(mesh, attribute="visibility", time=spark.birth, value=1)
    cmds.setKeyframe(mesh, attribute="visibility", time=spark.death, value=0)


def _emissive_surface(prefix, glow):
    surface = cmds.shadingNode("standardSurface", asShader=True, name=prefix + "_MTL")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=prefix + "_SG")
    cmds.connectAttr(surface + ".outColor", sg + ".surfaceShader")
    cmds.setAttr(surface + ".base", 0)
    cmds.setAttr(surface + ".specular", 0)
    cmds.setAttr(surface + ".emission", glow)
    cmds.setAttr(surface + ".thinWalled", 1)
    return surface, sg


def _ramp(name, ramp_type, entries):
    ramp = cmds.shadingNode("ramp", asTexture=True, name=name + "_ramp")
    place = cmds.shadingNode("place2dTexture", asUtility=True, name=name + "_place2d")
    cmds.connectAttr(place + ".outUV", ramp + ".uvCoord")
    cmds.connectAttr(place + ".outUvFilterSize", ramp + ".uvFilterSize")
    cmds.setAttr(ramp + ".type", ramp_type)
    cmds.setAttr(ramp + ".defaultColor", 0, 0, 0, type="double3")
    for index in cmds.getAttr(ramp + ".colorEntryList", multiIndices=True) or []:
        cmds.removeMultiInstance("{0}.colorEntryList[{1}]".format(ramp, index), b=True)
    for index, (position, color) in enumerate(entries):
        entry = "{0}.colorEntryList[{1}]".format(ramp, index)
        cmds.setAttr(entry + ".position", position)
        cmds.setAttr(entry + ".color", *color, type="double3")
    return ramp, place



def _connect_shading(group, nodes):
    for index, node in enumerate(nodes):
        cmds.connectAttr(
            node + ".message", "{0}.{1}[{2}]".format(group, SHADING_ATTR, index)
        )


def _unique_name(base):
    name = base
    counter = 1
    while cmds.objExists(name):
        name = "{0}{1}".format(base, counter)
        counter += 1
    return name
