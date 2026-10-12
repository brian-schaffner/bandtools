"""MXR Bass Synth preset schema and validation."""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class VoiceWaveform(str, Enum):
    """MXR oscillator waveform selection via VOICE button."""

    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    SQUARE = "square"


class TrackingMode(str, Enum):
    """MXR pitch tracking mode."""

    FIVE_STRING = "5string"
    FOUR_STRING = "4string"
    GUITAR = "guitar"


class OutputMode(str, Enum):
    """MXR output routing mode."""

    MONO = "mono"
    WET_DRY = "wet_dry"
    STEREO = "stereo"


class PresetSource(str, Enum):
    """How the preset data was acquired."""

    MANUAL = "manual"
    AUDIO = "audio"
    FACTORY = "factory"


class MXRPrimaryParams(BaseModel):
    """Primary knob parameters (direct access)."""

    mix: float = Field(0.5, ge=0.0, le=1.0, description="Dry/synth signal blend")
    sub_mix: float = Field(0.5, ge=0.0, le=1.0, description="Main to sub oscillator ratio")
    cutoff: float = Field(0.5, ge=0.0, le=1.0, description="Filter cutoff (normalized)")
    resonance: float = Field(0.0, ge=0.0, le=1.0, description="Filter resonance")
    envelope: float = Field(0.5, ge=0.0, le=1.0, description="Filter envelope attack/decay")
    mod: float = Field(0.0, ge=0.0, le=1.0, description="Modulation depth")


class MXRVoiceParams(BaseModel):
    """VOICE menu parameters (hold VOICE + turn knob)."""

    voice_mix: float = Field(0.5, ge=0.0, le=1.0, description="Main vs harmonic oscillators")
    noise_mix: float = Field(0.0, ge=0.0, le=1.0, description="Oscillator to noise ratio")
    filter_env_amount: float = Field(
        0.5, ge=-1.0, le=1.0, description="Filter envelope direction/depth"
    )
    glide: float = Field(0.0, ge=0.0, le=1.0, description="Portamento time")
    amp_envelope: float = Field(0.0, ge=0.0, le=1.0, description="Note attack time")
    mod_blend: float = Field(0.5, ge=0.0, le=1.0, description="Chorus vs filter LFO balance")


class MXRShapeParams(BaseModel):
    """SHAPE menu parameters (hold SHAPE + turn knob)."""

    compression: float = Field(0.0, ge=0.0, le=1.0, description="Compression amount")
    output_gain: float = Field(0.0, ge=-18.0, le=18.0, description="Output gain in dB")
    gate_sensitivity: float = Field(
        0.5, ge=0.0, le=1.0, description="GLOBAL: Note trigger threshold"
    )
    tracking: TrackingMode = Field(TrackingMode.FIVE_STRING, description="GLOBAL: Pitch tracking")
    dry_thru_fx: bool = Field(False, description="Process dry signal through effects")
    output_mode: OutputMode = Field(OutputMode.MONO, description="GLOBAL: Output routing")


class MXRSwitchStates(BaseModel):
    """Switch/button states."""

    voice_waveform: VoiceWaveform = Field(
        VoiceWaveform.SAWTOOTH, description="Oscillator waveform"
    )
    bypass: bool = Field(False, description="Effect bypass state")


class MXRExpressionState(BaseModel):
    """Expression pedal position state."""

    primary: MXRPrimaryParams = Field(default_factory=MXRPrimaryParams)
    voice: MXRVoiceParams = Field(default_factory=MXRVoiceParams)


class MXRExpression(BaseModel):
    """Expression pedal heel/toe configuration."""

    heel: MXRExpressionState = Field(default_factory=MXRExpressionState)
    toe: MXRExpressionState = Field(default_factory=MXRExpressionState)


class MXRPresetMetadata(BaseModel):
    """Metadata about preset acquisition."""

    source: PresetSource = Field(PresetSource.MANUAL, description="How preset was acquired")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence in parameter values")
    notes: str = Field("", description="User notes about the preset")
    factory_name: Optional[str] = Field(None, description="Original factory preset name if known")


class MXRPreset(BaseModel):
    """Complete MXR Bass Synth preset representation."""

    version: str = Field("1.0", description="Schema version")
    device: Literal["MXR_MB301"] = Field("MXR_MB301", description="Device identifier")
    id: str = Field(..., description="Unique preset identifier")
    name: str = Field(..., min_length=1, max_length=64, description="Preset name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    primary: MXRPrimaryParams = Field(default_factory=MXRPrimaryParams)
    voice: MXRVoiceParams = Field(default_factory=MXRVoiceParams)
    shape: MXRShapeParams = Field(default_factory=MXRShapeParams)
    switches: MXRSwitchStates = Field(default_factory=MXRSwitchStates)
    expression: Optional[MXRExpression] = Field(None, description="Expression pedal config")
    metadata: MXRPresetMetadata = Field(default_factory=MXRPresetMetadata)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Remove potentially problematic characters from preset name."""
        return v.strip().replace("/", "-").replace("\\", "-")

    def get_all_parameters(self) -> dict:
        """Return all parameters as a flat dictionary for analysis."""
        params = {}
        for name, value in self.primary.model_dump().items():
            params[f"primary.{name}"] = value
        for name, value in self.voice.model_dump().items():
            params[f"voice.{name}"] = value
        for name, value in self.shape.model_dump().items():
            if isinstance(value, Enum):
                params[f"shape.{name}"] = value.value
            else:
                params[f"shape.{name}"] = value
        for name, value in self.switches.model_dump().items():
            if isinstance(value, Enum):
                params[f"switches.{name}"] = value.value
            else:
                params[f"switches.{name}"] = value
        return params

    def get_normalized_vector(self) -> list[float]:
        """Return normalized parameter vector for optimization."""
        return [
            self.primary.mix,
            self.primary.sub_mix,
            self.primary.cutoff,
            self.primary.resonance,
            self.primary.envelope,
            self.primary.mod,
            self.voice.voice_mix,
            self.voice.noise_mix,
            (self.voice.filter_env_amount + 1.0) / 2.0,
            self.voice.glide,
            self.voice.amp_envelope,
            self.voice.mod_blend,
            self.shape.compression,
            (self.shape.output_gain + 18.0) / 36.0,
            {"triangle": 0.0, "sawtooth": 0.5, "square": 1.0}[self.switches.voice_waveform.value],
        ]
