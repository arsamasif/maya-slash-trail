"""Tests for slash_trail.sparks."""

import pytest

from slash_trail import ribbon
from slash_trail import sparks
from slash_trail import vecmath

TIMES = ribbon.sample_times(1, 5, 2)
BASE = [(0.0, 0.0, 0.0)] * len(TIMES)
TIPS = [(10.0 - index, float(index), 0.0) for index in range(len(TIMES))]


def _generate(seed=3, count=20):
    return sparks.generate(TIMES, BASE, TIPS, count, speed=2.0, life=6.0, seed=seed)


def test_count_order_and_window():
    result = _generate()
    assert len(result) == 20
    assert [spark.birth for spark in result] == sorted(spark.birth for spark in result)
    assert all(TIMES[1] <= spark.birth <= TIMES[-1] for spark in result)
    assert all(3.0 <= spark.life <= 6.0 for spark in result)


def test_same_seed_same_sparks():
    assert _generate(seed=5) == _generate(seed=5)
    assert _generate(seed=5) != _generate(seed=6)


def test_sparks_start_near_the_tip():
    for spark in _generate():
        assert spark.position[2] == pytest.approx(0.0)
        assert vecmath.length(spark.position) >= 0.85 * 7.0


def test_end_position_follows_velocity():
    spark = _generate(count=1)[0]
    expected = vecmath.add(spark.position, vecmath.scale(spark.velocity, spark.life))
    assert spark.end_position == pytest.approx(expected)


def test_streak_trails_behind_velocity():
    spark = sparks.Spark(1.0, 4.0, (0, 0, 0), (2.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    quad = sparks.streak(spark, length=3.0, width=0.2)
    assert quad.face_count == 1
    xs = [point[0] for point in quad.points]
    assert min(xs) == pytest.approx(-3.0)
    assert max(xs) == pytest.approx(0.0)
    assert quad.us == [0, 0, 1, 1]


def test_needs_two_samples():
    with pytest.raises(ValueError, match="two samples"):
        sparks.generate([1.0], BASE[:1], TIPS[:1], 3, 1.0, 1.0)
