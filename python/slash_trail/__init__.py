"""Turn any animated object into a glowing slash trail in Maya.

The core (settings, sampling times, ribbon mesh, reveal timing, sparks) is
pure Python and runs without Maya. ``maya_sample`` reads world positions
from a live scene, ``maya_build`` creates the mesh, shader and keys, and
``ui`` provides a Qt window for animators.

"""

__version__ = "1.0.0"
