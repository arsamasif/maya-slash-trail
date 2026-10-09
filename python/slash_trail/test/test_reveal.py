"""Tests for slash_trail.reveal."""

import pytest

from slash_trail import reveal

START, END, TRAIL = 10.0, 30.0, 5.0


def _u(frame):
    return (frame - START) / (END - START)


def test_blade_is_at_ramp_top_and_tail_at_bottom():
    current = 20.0
    assert reveal.ramp_position(_u(current), current, START, END, TRAIL) == pytest.approx(1.0)
    assert reveal.ramp_position(_u(current - TRAIL), current, START, END, TRAIL) == pytest.approx(0.0)


def test_future_and_old_parts_are_outside_the_ramp():
    current = 20.0
    assert reveal.ramp_position(_u(current + 1), current, START, END, TRAIL) > 1.0
    assert reveal.ramp_position(_u(current - TRAIL - 1), current, START, END, TRAIL) < 0.0


def test_keys_hide_before_start_and_drain_after_end():
    first, last = reveal.keys(START, END, TRAIL)
    width = reveal.coverage(START, END, TRAIL)
    assert first.frame == START
    assert first.translate_frame + width == pytest.approx(0.0)
    assert last.frame == END + TRAIL
    assert last.translate_frame == pytest.approx(1.0)


def test_keys_are_linear_in_between():
    first, last = reveal.keys(START, END, TRAIL)
    middle = (first.frame + last.frame) / 2
    expected = (first.translate_frame + last.translate_frame) / 2
    assert reveal.translate_frame(middle, START, END, TRAIL) == pytest.approx(expected)
