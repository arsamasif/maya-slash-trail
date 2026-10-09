"""Spark streaks that fly off the slash.

Sparks are born on the outer edge of the arc while the blade passes and
fly off along the swing direction, pushed a little outwards. Each one is a
thin quad stretched along its direction of travel, which reads as a motion
streak without any motion blur. Everything here is deterministic for a
given seed so a Rebuild gives the same sparks.

"""

import dataclasses
import random

from slash_trail import ribbon
from slash_trail import vecmath

OUTWARD_PUSH = 0.5
JITTER = 0.35


@dataclasses.dataclass(frozen=True)
class Spark:
    """One spark.

    Attributes:
        birth (float): Frame the spark appears.
        life (float): Frames it lives.
        position (tuple): World position at birth.
        velocity (tuple): World units per frame.
        normal (tuple): Normal of the swing plane at birth, used to give the
            streak a width that faces the swing.

    """

    birth: float
    life: float
    position: tuple
    velocity: tuple
    normal: tuple

    @property
    def death(self):
        """float: Frame the spark disappears."""
        return self.birth + self.life

    @property
    def end_position(self):
        """tuple: World position at death."""
        return vecmath.add(self.position, vecmath.scale(self.velocity, self.life))


def generate(times, base_points, tip_points, count, speed, life, seed=1):
    """Create sparks along the outer edge of the swing.

    Args:
        times (list): Sample frames.
        base_points (list): Blade base per sample.
        tip_points (list): Blade tip per sample.
        count (int): Number of sparks.
        speed (float): Average speed in units per frame.
        life (float): Longest lifetime in frames.
        seed (int): Random seed.

    Returns:
        list: ``Spark`` objects sorted by birth frame.

    Raises:
        ValueError: If there are fewer than two samples.

    """
    if len(times) < 2:
        raise ValueError("Sparks need at least two samples")
    rng = random.Random(seed)
    sparks = []
    for _ in range(count):
        index = rng.randint(1, len(times) - 1)
        base = base_points[index]
        tip = tip_points[index]
        tangent = vecmath.normalize(vecmath.sub(tip, tip_points[index - 1]))
        outward = vecmath.normalize(vecmath.sub(tip, base))
        jitter = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
        direction = vecmath.normalize(
            vecmath.add(
                vecmath.add(tangent, vecmath.scale(outward, OUTWARD_PUSH)),
                vecmath.scale(jitter, JITTER),
            )
        )
        sparks.append(
            Spark(
                birth=times[index],
                life=life * rng.uniform(0.5, 1.0),
                position=vecmath.lerp(base, tip, rng.uniform(0.85, 1.0)),
                velocity=vecmath.scale(direction, speed * rng.uniform(0.6, 1.3)),
                normal=vecmath.normalize(vecmath.cross(tangent, outward)),
            )
        )
    return sorted(sparks, key=lambda spark: spark.birth)


def streak(spark, length, width):
    """Build the streak quad for a spark, centred on its head.

    The quad points backwards along the velocity, so placing the mesh at the
    spark position and moving it along the velocity looks like a streak.

    Args:
        spark (Spark): The spark.
        length (float): Streak length.
        width (float): Streak width.

    Returns:
        ribbon.RibbonMesh: A single quad in the spark's local space.

    """
    direction = vecmath.normalize(spark.velocity)
    side = vecmath.normalize(vecmath.cross(direction, spark.normal), fallback=(1.0, 0.0, 0.0))
    tail = vecmath.scale(direction, -length)
    half = vecmath.scale(side, width * 0.5)
    origin = (0.0, 0.0, 0.0)
    return ribbon.build(
        [vecmath.sub(tail, half), vecmath.sub(origin, half)],
        [vecmath.add(tail, half), vecmath.add(origin, half)],
        inner=0.0,
    )
