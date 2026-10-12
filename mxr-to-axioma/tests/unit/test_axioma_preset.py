"""Tests for Axioma preset handling."""

import pytest
from src.device_adapters.axioma_preset import (
    AxiomaPreset,
    AxiomaOscillators,
    AxiomaFilter,
    AxiomaEnvelope,
    AxiomaMixer,
    Waveform,
    InstrumentMode,
)


class TestAxiomaOscillators:
    """Tests for AxiomaOscillators."""

    def test_default_values(self):
        osc = AxiomaOscillators()
        assert osc.osc1_waveform == Waveform.SAW
        assert osc.osc1_level == 1.0
        assert osc.osc2_level == 0.0
        assert osc.sub_level == 0.0

    def test_tuning_range(self):
        osc = AxiomaOscillators(osc2_tune=-24)
        assert osc.osc2_tune == -24

        osc = AxiomaOscillators(osc2_tune=24)
        assert osc.osc2_tune == 24

    def test_tuning_bounds(self):
        with pytest.raises(ValueError):
            AxiomaOscillators(osc2_tune=25)
        with pytest.raises(ValueError):
            AxiomaOscillators(osc2_tune=-25)

    def test_detune_range(self):
        osc = AxiomaOscillators(osc2_detune=-100)
        assert osc.osc2_detune == -100

        osc = AxiomaOscillators(osc2_detune=100)
        assert osc.osc2_detune == 100


class TestAxiomaFilter:
    """Tests for AxiomaFilter."""

    def test_default_values(self):
        filt = AxiomaFilter()
        assert filt.cutoff == 1.0
        assert filt.resonance == 0.0
        assert filt.env_amount == 0.0
        assert filt.env_decay == 0.5


class TestAxiomaPreset:
    """Tests for AxiomaPreset."""

    def test_create_preset(self):
        preset = AxiomaPreset(id="axioma-1", name="Test Axioma")
        assert preset.id == "axioma-1"
        assert preset.device == "DARKGLASS_AXIOMA"

    def test_get_all_parameters(self):
        preset = AxiomaPreset(
            id="axioma-1",
            name="Test",
            oscillators=AxiomaOscillators(osc1_level=0.8),
            filter=AxiomaFilter(cutoff=0.5),
        )
        params = preset.get_all_parameters()
        assert params["oscillators.osc1_level"] == 0.8
        assert params["filter.cutoff"] == 0.5

    def test_configuration_guide(self):
        preset = AxiomaPreset(
            id="axioma-1",
            name="Test Preset",
            oscillators=AxiomaOscillators(osc1_waveform=Waveform.SQUARE),
        )
        guide = preset.to_configuration_guide()
        assert "Test Preset" in guide
        assert "SQUARE" in guide
        assert "Oscillator Section" in guide
        assert "Filter Section" in guide

    def test_parameter_vector(self):
        preset = AxiomaPreset(id="test", name="Test")
        vector = preset.get_parameter_vector()
        assert isinstance(vector, list)
        assert len(vector) == 14  # All optimizable parameters
