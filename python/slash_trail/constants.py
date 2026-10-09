"""Shared constants for the slash_trail package.

Default settings, node and attribute names, and the gradients used by the
trail shader. Nothing in here imports Maya.

"""

DEFAULT_TRAIL_FRAMES = 6.0
DEFAULT_SUBSTEPS = 4
DEFAULT_INNER = 0.35
DEFAULT_COLOR = (0.25, 0.45, 1.0)
DEFAULT_GLOW = 3.0
DEFAULT_CORE_WHITE = 0.75
DEFAULT_AXIS = "y"
DEFAULT_LENGTH = 10.0
DEFAULT_SPARK_COUNT = 12
DEFAULT_SPARK_SPEED = 30.0
DEFAULT_SPARK_LIFE = 8.0

# A spark streak is as long as the distance it travels in this many frames,
# which reads like motion blur, and its width is a fraction of that length.
SPARK_STREAK_FRAMES = 0.75
SPARK_WIDTH_RATIO = 0.08

DEFAULT_WIDTH = 2.0
DEFAULT_FACING = "camera"
DEFAULT_CAMERA = "persp"

AXES = ("x", "y", "z", "-x", "-y", "-z")

# How a point trail (no blade) orients its width: towards a camera, or along
# one of the object's own axes.
CAMERA_FACING = "camera"
FACINGS = (CAMERA_FACING, "x", "y", "z")

# Upper limit of samples per trail; keeps a typo in the range from building
# a mesh with millions of faces.
MAX_SAMPLES = 20000

GROUP_SUFFIX = "_slashTrail"
SETTINGS_ATTR = "slashTrailSettings"
MESH_NAME = "trailMesh"
SPARKS_NAME = "sparks"

# Opacity along the trail age: 0 is the tail end, 1 is the blade.
AGE_GRADIENT = (
    (0.0, 0.0),
    (0.5, 0.15),
    (0.88, 0.75),
    (1.0, 1.0),
)

# Opacity across the blade: 0 is the inner edge, 1 is the blade tip. Most of
# the energy sits in a thin band near the tip, like a crescent.
EDGE_GRADIENT = (
    (0.0, 0.0),
    (0.6, 0.2),
    (0.93, 1.0),
    (1.0, 0.5),
)

# Opacity across a point trail: brightest along the object's path in the
# middle, fading out to both edges.
CENTER_EDGE_GRADIENT = (
    (0.0, 0.0),
    (0.35, 0.3),
    (0.5, 1.0),
    (0.65, 0.3),
    (1.0, 0.0),
)

# Emission brightness across the blade, multiplied with the glow color;
# the tip end is blended towards white by ``core_white``.
CORE_GRADIENT = (
    (0.0, 0.35),
    (0.8, 1.0),
)
