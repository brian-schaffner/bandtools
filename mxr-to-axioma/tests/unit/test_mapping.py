"""Tests for parameter mapping and translation."""

import pytest
from src.preset_parsers.mxr_preset import (
    MXRPreset,
    MXRPrimaryParams,
    MXRVoiceParams,
    MXRShapeParams,
    MXRSwitchStates,
    VoiceWaveform,
    TrackingMode,
)
from src.device_adapters.mapping import (
    translate_mxr_to_axioma,
    map_waveform,
    map_tracking_mode,
)
from src.device_adapters.axioma_preset import Waveform, InstrumentMode


class TestWaveformMapping:
    """Tests for waveform mapping."""

    def test_triangle_mapping(self):
        assert map_waveform(VoiceWaveform.TRIANGLE) == Waveform.TRIANGLE

    def test_sawtooth_mapping(self):
        assert map_waveform(VoiceWaveform.SAWTOOTH) == Waveform.SAW

    def test_square_mapping(self):
        assert map_waveform(VoiceWaveform.SQUARE) == Waveform.SQUARE


class TestTrackingMapping:
    """Tests for tracking mode mapping."""

    def test_5string_mapping(self):
        assert map_tracking_mode(TrackingMode.FIVE_STRING) == InstrumentMode.FIVE_STRING

    def test_4string_mapping(self):
        assert map_tracking_mode(TrackingMode.FOUR_STRING) == InstrumentMode.FOUR_STRING

    def test_guitar_mapping(self):
        assert map_tracking_mode(TrackingMode.GUITAR) == InstrumentMode.GUITAR


class TestTranslation:
    """Tests for full preset translation."""

    def test_basic_translation(self):
        mxr = MXRPreset(
            id="mxr-1",
            name="Test MXR",
            primary=MXRPrimaryParams(mix=0.8, cutoff=0.6, resonance=0.4),
            switches=MXRSwitchStates(voice_waveform=VoiceWaveform.SAWTOOTH),
        )
        axioma = translate_mxr_to_axioma(mxr)

        assert axioma.name == "Test MXR (Axioma)"
        assert axioma.oscillators.osc1_waveform == Waveform.SAW
        assert axioma.mixer.blend == 0.8
        assert axioma.filter.cutoff == 0.6
        assert axioma.filter.resonance == 0.4

    def test_translation_has_metadata(self):
        mxr = MXRPreset(id="mxr-1", name="Test")
        axioma = translate_mxr_to_axioma(mxr)

        assert axioma.translation is not None
        assert axioma.translation.source_preset_id == "mxr-1"
        assert axioma.translation.mapping_version == "1.0"
        assert len(axioma.translation.approximations) > 0

    def test_glide_creates_gap(self):
        mxr = MXRPreset(
            id="mxr-1",
            name="Test",
            voice=MXRVoiceParams(glide=0.5),
        )
        axioma = translate_mxr_to_axioma(mxr)

        gaps = [g.feature for g in axioma.translation.gaps]
        assert "Glide/Portamento" in gaps

    def test_modulation_creates_gap_and_block(self):
        mxr = MXRPreset(
            id="mxr-1",
            name="Test",
            primary=MXRPrimaryParams(mod=0.5),
        )
        axioma = translate_mxr_to_axioma(mxr)

        gaps = [g.feature for g in axioma.translation.gaps]
        assert "LFO Modulation" in gaps

        blocks = [b.block_type for b in axioma.translation.additional_blocks]
        assert "Chorus/Modulation" in blocks

    def test_compression_creates_block(self):
        mxr = MXRPreset(
            id="mxr-1",
            name="Test",
            shape=MXRShapeParams(compression=0.6),
        )
        axioma = translate_mxr_to_axioma(mxr)

        blocks = [b.block_type for b in axioma.translation.additional_blocks]
        assert "Compressor" in blocks

    def test_confidence_score(self):
        mxr = MXRPreset(id="mxr-1", name="Test")
        axioma = translate_mxr_to_axioma(mxr)

        assert 0.0 <= axioma.translation.overall_confidence <= 1.0
