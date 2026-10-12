"""Tests for MXR preset parsing and validation."""

import pytest
from src.preset_parsers.mxr_preset import (
    MXRPreset,
    MXRPrimaryParams,
    MXRVoiceParams,
    MXRShapeParams,
    MXRSwitchStates,
    VoiceWaveform,
    TrackingMode,
    OutputMode,
)


class TestMXRPrimaryParams:
    """Tests for MXRPrimaryParams."""

    def test_default_values(self):
        params = MXRPrimaryParams()
        assert params.mix == 0.5
        assert params.sub_mix == 0.5
        assert params.cutoff == 0.5
        assert params.resonance == 0.0
        assert params.envelope == 0.5
        assert params.mod == 0.0

    def test_custom_values(self):
        params = MXRPrimaryParams(
            mix=0.8,
            sub_mix=0.6,
            cutoff=0.7,
            resonance=0.4,
            envelope=0.3,
            mod=0.2,
        )
        assert params.mix == 0.8
        assert params.resonance == 0.4

    def test_value_bounds(self):
        with pytest.raises(ValueError):
            MXRPrimaryParams(mix=1.5)
        with pytest.raises(ValueError):
            MXRPrimaryParams(cutoff=-0.1)


class TestMXRVoiceParams:
    """Tests for MXRVoiceParams."""

    def test_filter_env_amount_range(self):
        params = MXRVoiceParams(filter_env_amount=-0.5)
        assert params.filter_env_amount == -0.5

        params = MXRVoiceParams(filter_env_amount=0.8)
        assert params.filter_env_amount == 0.8

    def test_filter_env_bounds(self):
        with pytest.raises(ValueError):
            MXRVoiceParams(filter_env_amount=1.5)
        with pytest.raises(ValueError):
            MXRVoiceParams(filter_env_amount=-1.5)


class TestMXRShapeParams:
    """Tests for MXRShapeParams."""

    def test_output_gain_range(self):
        params = MXRShapeParams(output_gain=-18.0)
        assert params.output_gain == -18.0

        params = MXRShapeParams(output_gain=18.0)
        assert params.output_gain == 18.0

    def test_tracking_modes(self):
        params = MXRShapeParams(tracking=TrackingMode.FOUR_STRING)
        assert params.tracking == TrackingMode.FOUR_STRING

    def test_output_modes(self):
        params = MXRShapeParams(output_mode=OutputMode.STEREO)
        assert params.output_mode == OutputMode.STEREO


class TestMXRPreset:
    """Tests for MXRPreset."""

    def test_create_preset(self):
        preset = MXRPreset(id="test-1", name="Test Preset")
        assert preset.id == "test-1"
        assert preset.name == "Test Preset"
        assert preset.device == "MXR_MB301"

    def test_name_sanitization(self):
        preset = MXRPreset(id="test-1", name="Test/Preset\\Name")
        assert preset.name == "Test-Preset-Name"

    def test_get_all_parameters(self):
        preset = MXRPreset(
            id="test-1",
            name="Test",
            primary=MXRPrimaryParams(mix=0.7),
            switches=MXRSwitchStates(voice_waveform=VoiceWaveform.SQUARE),
        )
        params = preset.get_all_parameters()
        assert params["primary.mix"] == 0.7
        assert params["switches.voice_waveform"] == "square"

    def test_normalized_vector(self):
        preset = MXRPreset(
            id="test-1",
            name="Test",
            primary=MXRPrimaryParams(mix=1.0, cutoff=0.0),
        )
        vector = preset.get_normalized_vector()
        assert isinstance(vector, list)
        assert len(vector) == 15
        assert vector[0] == 1.0  # mix
        assert vector[2] == 0.0  # cutoff
