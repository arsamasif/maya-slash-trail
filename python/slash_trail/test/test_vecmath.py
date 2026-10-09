"""Tests for slash_trail.vecmath."""

import pytest

from slash_trail import vecmath


def test_basic_arithmetic():
    assert vecmath.add((1, 2, 3), (1, 1, 1)) == (2, 3, 4)
    assert vecmath.sub((1, 2, 3), (1, 1, 1)) == (0, 1, 2)
    assert vecmath.scale((1, 2, 3), 2) == (2, 4, 6)
    assert vecmath.lerp((0, 0, 0), (10, 20, 30), 0.5) == (5, 10, 15)


def test_dot_and_cross():
    assert vecmath.dot((1, 0, 0), (0, 1, 0)) == 0
    assert vecmath.cross((1, 0, 0), (0, 1, 0)) == (0, 0, 1)


def test_normalize():
    assert vecmath.length(vecmath.normalize((3, 4, 0))) == pytest.approx(1.0)
    assert vecmath.normalize((0, 0, 0), fallback=(1, 0, 0)) == (1, 0, 0)
