"""Tests for slash_trail.settings."""

import pytest

from slash_trail import settings


def make(**overrides):
    values = {"base": "sword", "use_blade": True, "tip": "swordTip", "start": 1, "end": 11}
    values.update(overrides)
    return settings.TrailSettings(**values)


def test_valid_settings_pass():
    make().validate()
    make(tip="", axis="-z", length=5).validate()
    make(use_blade=False, tip="").validate()
    make(use_blade=False, facing="z", camera="").validate()


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"base": ""}, "Pick an object"),
        ({"tip": "sword"}, "different objects"),
        ({"tip": "", "axis": "w"}, "Axis must be"),
        ({"tip": "", "length": 0}, "length must be positive"),
        ({"end": 1}, "after the start"),
        ({"trail_frames": 0}, "Trail length"),
        ({"substeps": 0}, "Substeps"),
        ({"end": 100000, "substeps": 32}, "too many"),
        ({"inner": 1.0}, "Inner edge"),
        ({"use_blade": False, "width": 0}, "width must be positive"),
        ({"use_blade": False, "facing": "up"}, "Facing must be"),
        ({"use_blade": False, "camera": ""}, "Pick a camera"),
        ({"sparks": True, "spark_count": 0}, "Sparks need"),
    ],
)
def test_invalid_settings(overrides, message):
    with pytest.raises(ValueError, match=message):
        make(**overrides).validate()


def test_sample_count_includes_both_ends():
    assert make(start=1, end=11, substeps=4).sample_count == 41


def test_trail_name_from_base():
    assert make(base="|rig|char:sword_ctl").trail_name == "char_sword_ctl"
    assert make(name="heroSlash").trail_name == "heroSlash"


def test_json_round_trip():
    original = make(color=(1, 0.5, 0), sparks=True, seed=7)
    restored = settings.TrailSettings.from_json(original.to_json())
    assert restored == original
    assert restored.color == (1.0, 0.5, 0.0)


def test_point_trail_ignores_blade_fields():
    make(use_blade=False, tip="sword", axis="w", length=0).validate()


def test_settings_saved_before_use_blade_load_as_blades():
    assert settings.TrailSettings.from_json('{"base": "a", "tip": "b"}').use_blade
    assert not settings.TrailSettings().use_blade


def test_from_json_ignores_unknown_keys():
    restored = settings.TrailSettings.from_json('{"base": "a", "future_option": 3}')
    assert restored.base == "a"


def test_from_json_rejects_non_objects():
    with pytest.raises(ValueError, match="JSON object"):
        settings.TrailSettings.from_json("[1, 2]")
