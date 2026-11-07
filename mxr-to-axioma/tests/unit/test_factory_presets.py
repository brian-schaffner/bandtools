"""Tests for factory preset library."""

import pytest
from src.preset_parsers.mxr_factory import (
    get_factory_preset,
    list_factory_presets,
    MXR_FACTORY_PRESETS,
)
from src.preset_parsers.mxr_preset import PresetSource


class TestFactoryPresets:
    """Tests for factory preset retrieval."""

    def test_list_factory_presets(self):
        presets = list_factory_presets()
        assert len(presets) == 8
        assert all("name" in p and "description" in p for p in presets)

    def test_all_factory_presets_exist(self):
        expected_names = [
            "THRILLENGANES",
            "WONDERFUL",
            "LIZARD SYNTH",
            "SYNTHADELIC",
            "SLEDGE",
            "ARMY OF SYNTH",
            "NINE INCH SYNTH",
            "SYNTHMAU5",
        ]
        for name in expected_names:
            assert name in MXR_FACTORY_PRESETS

    def test_get_factory_preset_by_name(self):
        preset = get_factory_preset("THRILLENGANES")
        assert preset is not None
        assert preset.name == "THRILLENGANES"
        assert preset.metadata.source == PresetSource.FACTORY

    def test_get_factory_preset_case_insensitive(self):
        preset = get_factory_preset("thrillenganes")
        assert preset is not None
        assert preset.name == "THRILLENGANES"

    def test_get_nonexistent_preset(self):
        preset = get_factory_preset("NONEXISTENT")
        assert preset is None

    def test_factory_preset_has_description(self):
        preset = get_factory_preset("SLEDGE")
        assert preset.metadata.notes != ""
        assert "Peter Gabriel" in preset.metadata.notes

    def test_factory_preset_parameters_valid(self):
        for name in MXR_FACTORY_PRESETS:
            preset = get_factory_preset(name)
            assert preset is not None
            assert 0 <= preset.primary.mix <= 1
            assert 0 <= preset.primary.cutoff <= 1
            assert 0 <= preset.primary.resonance <= 1
            vector = preset.get_normalized_vector()
            assert all(0 <= v <= 1 for v in vector)
