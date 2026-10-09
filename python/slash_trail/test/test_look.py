"""Tests for slash_trail.look."""

from slash_trail import look
from slash_trail import settings


def _brightest(entries):
    return max(entries, key=lambda entry: sum(entry[1]))[0]


def test_blade_trail_is_brightest_at_the_tip():
    blade = settings.TrailSettings(use_blade=True)
    assert _brightest(look.core_entries(blade)) == 1.0
    edge = look.edge_entries(blade)
    assert 0.9 <= _brightest(edge) < 1.0
    assert edge[0][1] == (0.0, 0.0, 0.0)


def test_point_trail_is_brightest_in_the_middle():
    point = settings.TrailSettings(use_blade=False)
    assert _brightest(look.core_entries(point)) == 0.5
    edge = look.edge_entries(point)
    assert _brightest(edge) == 0.5
    assert edge[0][1] == edge[-1][1] == (0.0, 0.0, 0.0)


def test_core_white_blends_towards_white():
    plain = settings.TrailSettings(color=(0.0, 0.0, 1.0), core_white=0.0)
    hot = settings.TrailSettings(color=(0.0, 0.0, 1.0), core_white=1.0)
    assert dict(look.core_entries(plain))[0.5] == (0.0, 0.0, 1.0)
    assert dict(look.core_entries(hot))[0.5] == (1.0, 1.0, 1.0)


def test_age_entries_run_from_hidden_tail_to_full_head():
    entries = look.age_entries()
    assert entries[0] == (0.0, (0.0, 0.0, 0.0))
    assert entries[-1] == (1.0, (1.0, 1.0, 1.0))
