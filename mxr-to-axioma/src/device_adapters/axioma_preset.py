"""Darkglass Anagram Axioma preset schema."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Waveform(str, Enum):
    """Oscillator waveform types."""

    SAW = "saw"
    SQUARE = "square"
    TRIANGLE = "triangle"


class ArpDirection(str, Enum):
    """Arpeggiator direction modes."""

    UP = "up"
    DOWN = "down"
    UP_DOWN = "up_down"
    RANDOM = "random"


class ArpChordType(str, Enum):
    """Arpeggiator chord types."""

    MAJOR = "major"
    MINOR = "minor"
    MAJ7 = "maj7"
    MIN7 = "min7"
    MINMAJ7 = "minmaj7"


class InstrumentMode(str, Enum):
    """Pitch tracking instrument modes."""

    FOUR_STRING = "4string"
    FIVE_STRING = "5string"
    EXTENDED = "extended"
    GUITAR = "guitar"
    BARITONE = "baritone"


class MappingConfidence(str, Enum):
    """Confidence level for parameter mapping."""

    DIRECT = "direct"
    APPROXIMATE = "approximate"
    ESTIMATED = "estimated"
    GAP = "gap"


class AxiomaOscillators(BaseModel):
    """Axioma oscillator section parameters."""

    osc1_waveform: Waveform = Field(Waveform.SAW, description="Oscillator 1 waveform")
    osc1_level: float = Field(1.0, ge=0.0, le=1.0, description="Oscillator 1 level")
    osc2_waveform: Waveform = Field(Waveform.SAW, description="Oscillator 2 waveform")
    osc2_level: float = Field(0.0, ge=0.0, le=1.0, description="Oscillator 2 level")
    osc2_tune: int = Field(0, ge=-24, le=24, description="Oscillator 2 semitone offset")
    osc2_detune: float = Field(0.0, ge=-100.0, le=100.0, description="Oscillator 2 detune in cents")
    sub_level: float = Field(0.0, ge=0.0, le=1.0, description="Sub oscillator level")


class AxiomaFilter(BaseModel):
    """Axioma filter section parameters."""

    cutoff: float = Field(1.0, ge=0.0, le=1.0, description="Filter cutoff (normalized)")
    resonance: float = Field(0.0, ge=0.0, le=1.0, description="Filter resonance")
    env_amount: float = Field(0.0, ge=0.0, le=1.0, description="Filter envelope amount")
    env_decay: float = Field(0.5, ge=0.0, le=1.0, description="Filter envelope decay")


class AxiomaEnvelope(BaseModel):
    """Axioma amplitude envelope parameters."""

    attack: float = Field(0.0, ge=0.0, le=1.0, description="Attack time")
    release: float = Field(0.3, ge=0.0, le=1.0, description="Release time")


class AxiomaMixer(BaseModel):
    """Axioma mixer/blend parameters."""

    blend: float = Field(1.0, ge=0.0, le=1.0, description="Dry/synth blend (1.0 = full synth)")


class AxiomaArpeggiator(BaseModel):
    """Axioma arpeggiator parameters."""

    enabled: bool = Field(False, description="Arpeggiator on/off")
    direction: ArpDirection = Field(ArpDirection.UP, description="Arpeggio direction")
    chord_type: ArpChordType = Field(ArpChordType.MAJOR, description="Chord type")
    octaves: int = Field(1, ge=1, le=3, description="Number of octaves")
    tempo: float = Field(120.0, ge=40.0, le=300.0, description="Tempo in BPM")


class ParameterApproximation(BaseModel):
    """Documentation of a parameter approximation."""

    source_param: str = Field(..., description="Source MXR parameter name")
    target_param: str = Field(..., description="Target Axioma parameter name")
    confidence: MappingConfidence = Field(..., description="Mapping confidence")
    notes: str = Field("", description="Explanation of approximation")
    source_value: float = Field(..., description="Original MXR value")
    target_value: float = Field(..., description="Mapped Axioma value")


class FeatureGap(BaseModel):
    """Documentation of unmappable MXR feature."""

    feature: str = Field(..., description="MXR feature name")
    reason: str = Field(..., description="Why it cannot be mapped")
    workaround: Optional[str] = Field(None, description="Suggested workaround if any")


class AdditionalBlock(BaseModel):
    """Suggested additional Anagram block to approximate MXR behavior."""

    block_type: str = Field(..., description="Anagram block type")
    purpose: str = Field(..., description="What MXR feature it approximates")
    suggested_settings: dict = Field(default_factory=dict, description="Recommended settings")


class TranslationMetadata(BaseModel):
    """Metadata about the translation process."""

    source_preset_id: str = Field(..., description="ID of source MXR preset")
    source_preset_name: str = Field(..., description="Name of source MXR preset")
    mapping_version: str = Field("1.0", description="Translation algorithm version")
    translated_at: datetime = Field(default_factory=datetime.utcnow)
    approximations: list[ParameterApproximation] = Field(
        default_factory=list, description="List of approximated parameters"
    )
    gaps: list[FeatureGap] = Field(
        default_factory=list, description="List of unmappable features"
    )
    additional_blocks: list[AdditionalBlock] = Field(
        default_factory=list, description="Suggested additional Anagram blocks"
    )
    overall_confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Overall translation confidence"
    )


class AxiomaPreset(BaseModel):
    """Complete Darkglass Axioma preset representation."""

    version: str = Field("1.0", description="Schema version")
    device: Literal["DARKGLASS_AXIOMA"] = Field("DARKGLASS_AXIOMA", description="Device identifier")
    id: str = Field(..., description="Unique preset identifier")
    name: str = Field(..., min_length=1, max_length=64, description="Preset name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    oscillators: AxiomaOscillators = Field(default_factory=AxiomaOscillators)
    filter: AxiomaFilter = Field(default_factory=AxiomaFilter)
    envelope: AxiomaEnvelope = Field(default_factory=AxiomaEnvelope)
    mixer: AxiomaMixer = Field(default_factory=AxiomaMixer)
    arpeggiator: AxiomaArpeggiator = Field(default_factory=AxiomaArpeggiator)
    instrument_mode: InstrumentMode = Field(
        InstrumentMode.FIVE_STRING, description="Pitch tracking mode"
    )
    translation: Optional[TranslationMetadata] = Field(
        None, description="Translation metadata if converted from another device"
    )

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Remove potentially problematic characters from preset name."""
        return v.strip().replace("/", "-").replace("\\", "-")

    def get_all_parameters(self) -> dict:
        """Return all parameters as a flat dictionary."""
        params = {}
        for name, value in self.oscillators.model_dump().items():
            if isinstance(value, Enum):
                params[f"oscillators.{name}"] = value.value
            else:
                params[f"oscillators.{name}"] = value
        for name, value in self.filter.model_dump().items():
            params[f"filter.{name}"] = value
        for name, value in self.envelope.model_dump().items():
            params[f"envelope.{name}"] = value
        for name, value in self.mixer.model_dump().items():
            params[f"mixer.{name}"] = value
        params["instrument_mode"] = self.instrument_mode.value
        return params

    def get_parameter_vector(self) -> list[float]:
        """Return parameter vector for optimization."""
        waveform_map = {"saw": 0.0, "square": 0.5, "triangle": 1.0}
        return [
            waveform_map[self.oscillators.osc1_waveform.value],
            self.oscillators.osc1_level,
            waveform_map[self.oscillators.osc2_waveform.value],
            self.oscillators.osc2_level,
            (self.oscillators.osc2_tune + 24) / 48,
            (self.oscillators.osc2_detune + 100) / 200,
            self.oscillators.sub_level,
            self.filter.cutoff,
            self.filter.resonance,
            self.filter.env_amount,
            self.filter.env_decay,
            self.envelope.attack,
            self.envelope.release,
            self.mixer.blend,
        ]

    def to_configuration_guide(self) -> str:
        """Generate human-readable configuration guide for Darkglass Suite."""
        lines = [
            f"# Axioma Preset Configuration: {self.name}",
            "",
            "## Oscillator Section",
            f"- OSC 1 Waveform: {self.oscillators.osc1_waveform.value.upper()}",
            f"- OSC 1 Level: {self.oscillators.osc1_level * 100:.0f}%",
            f"- OSC 2 Waveform: {self.oscillators.osc2_waveform.value.upper()}",
            f"- OSC 2 Level: {self.oscillators.osc2_level * 100:.0f}%",
            f"- OSC 2 Tune: {self.oscillators.osc2_tune:+d} semitones",
            f"- OSC 2 Detune: {self.oscillators.osc2_detune:+.0f} cents",
            f"- SUB Level: {self.oscillators.sub_level * 100:.0f}%",
            "",
            "## Filter Section",
            f"- Cutoff: {self.filter.cutoff * 100:.0f}%",
            f"- Resonance: {self.filter.resonance * 100:.0f}%",
            f"- Envelope Amount: {self.filter.env_amount * 100:.0f}%",
            f"- Envelope Decay: {self.filter.env_decay * 100:.0f}%",
            "",
            "## Envelope Section",
            f"- Attack: {self.envelope.attack * 100:.0f}%",
            f"- Release: {self.envelope.release * 100:.0f}%",
            "",
            "## Mixer",
            f"- Blend (Dry/Synth): {self.mixer.blend * 100:.0f}% synth",
            "",
            f"## Instrument Mode: {self.instrument_mode.value}",
        ]

        if self.translation:
            lines.extend([
                "",
                "---",
                "",
                "## Translation Notes",
                "",
                f"Translated from: {self.translation.source_preset_name}",
                f"Overall confidence: {self.translation.overall_confidence * 100:.0f}%",
            ])

            if self.translation.approximations:
                lines.extend(["", "### Parameter Approximations"])
                for approx in self.translation.approximations:
                    lines.append(
                        f"- {approx.source_param} → {approx.target_param}: "
                        f"{approx.confidence.value} ({approx.notes})"
                    )

            if self.translation.gaps:
                lines.extend(["", "### Unmapped Features"])
                for gap in self.translation.gaps:
                    workaround = f" Workaround: {gap.workaround}" if gap.workaround else ""
                    lines.append(f"- {gap.feature}: {gap.reason}{workaround}")

            if self.translation.additional_blocks:
                lines.extend(["", "### Suggested Additional Blocks"])
                for block in self.translation.additional_blocks:
                    lines.append(f"- {block.block_type}: {block.purpose}")

        return "\n".join(lines)
