"""Settings for one slash trail.

``TrailSettings`` holds everything needed to build (and later rebuild) a
trail: which object drives it, the frame range, the look and the sparks.
By default a trail follows one object's pivot; with ``use_blade`` it is
swept between a blade base and tip, like a sword slash.
It serializes to JSON so the Maya side can store it on the trail group and
the Rebuild button can recreate the trail after the animation changed.

"""

import dataclasses
import json

from slash_trail import constants


@dataclasses.dataclass
class TrailSettings:
    """Inputs for one trail.

    Attributes:
        base (str): Object that drives the trail; the blade base when
            ``use_blade`` is on.
        use_blade (bool): Sweep the trail between a blade base and tip
            instead of following the object's pivot.
        width (float): Ribbon width of a point trail (no blade).
        facing (str): How a point trail orients its width: ``"camera"`` or
            one of the object's axes ``"x"``, ``"y"``, ``"z"``.
        camera (str): Camera a ``"camera"`` facing trail turns towards.
        tip (str): Object at the blade tip. Empty means "use ``axis`` and
            ``length`` in the base object's local space".
        axis (str): Local axis of the base pointing at the tip, e.g. ``"y"``.
        length (float): Blade length along ``axis`` when there is no tip.
        start (float): First frame of the swing.
        end (float): Last frame of the swing.
        trail_frames (float): How many frames the trail lingers behind.
        substeps (int): Samples per frame; more gives a smoother arc.
        inner (float): Where the ribbon starts along the blade, 0 at the
            base and 1 at the tip.
        color (tuple): RGB glow color, 0-1.
        glow (float): Emission strength.
        core_white (float): How white-hot the tip edge gets, 0-1.
        sparks (bool): Add spark streaks flying off the arc.
        spark_count (int): Number of sparks.
        spark_speed (float): Spark speed in scene units per frame.
        spark_life (float): Spark lifetime in frames.
        seed (int): Random seed so sparks rebuild the same way.
        name (str): Trail name; defaults to the base object's name.

    """

    base: str = ""
    use_blade: bool = False
    width: float = constants.DEFAULT_WIDTH
    facing: str = constants.DEFAULT_FACING
    camera: str = constants.DEFAULT_CAMERA
    tip: str = ""
    axis: str = constants.DEFAULT_AXIS
    length: float = constants.DEFAULT_LENGTH
    start: float = 1.0
    end: float = 24.0
    trail_frames: float = constants.DEFAULT_TRAIL_FRAMES
    substeps: int = constants.DEFAULT_SUBSTEPS
    inner: float = constants.DEFAULT_INNER
    color: tuple = constants.DEFAULT_COLOR
    glow: float = constants.DEFAULT_GLOW
    core_white: float = constants.DEFAULT_CORE_WHITE
    sparks: bool = False
    spark_count: int = constants.DEFAULT_SPARK_COUNT
    spark_speed: float = constants.DEFAULT_SPARK_SPEED
    spark_life: float = constants.DEFAULT_SPARK_LIFE
    seed: int = 1
    name: str = ""

    def __post_init__(self):
        self.color = tuple(float(value) for value in self.color)

    @property
    def sample_count(self):
        """int: Number of samples from start to end, both included."""
        return int(round((self.end - self.start) * self.substeps)) + 1

    @property
    def trail_name(self):
        """str: Name for the trail group, without the suffix."""
        if self.name:
            return self.name
        return self.base.rsplit("|", 1)[-1].replace(":", "_") or "slash"

    def validate(self):
        """Check the settings and raise on the first problem.

        Raises:
            ValueError: If a value is missing or out of range.

        """
        if not self.base:
            raise ValueError("Pick an object to drive the trail")
        if self.use_blade:
            self._validate_blade()
        else:
            self._validate_point()
        if self.end <= self.start:
            raise ValueError("End frame must be after the start frame")
        if self.trail_frames <= 0:
            raise ValueError("Trail length must be at least a fraction of a frame")
        if self.substeps < 1:
            raise ValueError("Substeps must be 1 or more")
        if self.sample_count > constants.MAX_SAMPLES:
            raise ValueError(
                "{0} samples is too many, lower the substeps or the range".format(
                    self.sample_count
                )
            )
        if not 0.0 <= self.inner < 1.0:
            raise ValueError("Inner edge must be between 0 and 1")
        if len(self.color) != 3:
            raise ValueError("Color needs three values")
        if self.sparks and (self.spark_count < 1 or self.spark_life <= 0):
            raise ValueError("Sparks need a count and a life above zero")

    def _validate_blade(self):
        if self.tip and self.tip == self.base:
            raise ValueError("Base and tip must be different objects")
        if not self.tip and self.axis not in constants.AXES:
            raise ValueError(
                "Axis must be one of {0}, got '{1}'".format(", ".join(constants.AXES), self.axis)
            )
        if not self.tip and self.length <= 0:
            raise ValueError("Blade length must be positive")

    def _validate_point(self):
        if self.width <= 0:
            raise ValueError("Trail width must be positive")
        if self.facing not in constants.FACINGS:
            raise ValueError(
                "Facing must be one of {0}, got '{1}'".format(
                    ", ".join(constants.FACINGS), self.facing
                )
            )
        if self.facing == constants.CAMERA_FACING and not self.camera:
            raise ValueError("Pick a camera for the trail to face")

    def to_json(self):
        """Serialize to a JSON string.

        Returns:
            str: JSON object with one key per field.

        """
        return json.dumps(dataclasses.asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, text):
        """Build settings from ``to_json`` output.

        Unknown keys are ignored so trails built by a newer version still
        load in an older one. Settings saved before ``use_blade`` existed
        were always blade trails, so they load with it on.

        Args:
            text (str): JSON string.

        Returns:
            TrailSettings: The settings.

        Raises:
            ValueError: If the text is not a JSON object.

        """
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Trail settings must be a JSON object")
        data.setdefault("use_blade", True)
        names = {field.name for field in dataclasses.fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in names})
