"""Parameter mapping engine for MXR to Axioma translation."""

import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from ..preset_parsers.mxr_preset import (
    MXRPreset,
    VoiceWaveform,
    TrackingMode,
)
from .axioma_preset import (
    AxiomaPreset,
    AxiomaOscillators,
    AxiomaFilter,
    AxiomaEnvelope,
    AxiomaMixer,
    AxiomaArpeggiator,
    Waveform,
    InstrumentMode,
    MappingConfidence,
    ParameterApproximation,
    FeatureGap,
    AdditionalBlock,
    TranslationMetadata,
)


@dataclass
class ParameterMapping:
    """Definition of a single parameter mapping."""

    source_path: str
    target_path: str
    confidence: MappingConfidence
    transform: Optional[Callable[[float], float]] = None
    notes: str = ""


class MappingReport:
    """Report generated during translation."""

    def __init__(self):
        self.approximations: list[ParameterApproximation] = []
        self.gaps: list[FeatureGap] = []
        self.additional_blocks: list[AdditionalBlock] = []

    def add_approximation(
        self,
        source_param: str,
        target_param: str,
        confidence: MappingConfidence,
        source_value: float,
        target_value: float,
        notes: str = "",
    ):
        self.approximations.append(
            ParameterApproximation(
                source_param=source_param,
                target_param=target_param,
                confidence=confidence,
                source_value=source_value,
                target_value=target_value,
                notes=notes,
            )
        )

    def add_gap(self, feature: str, reason: str, workaround: Optional[str] = None):
        self.gaps.append(FeatureGap(feature=feature, reason=reason, workaround=workaround))

    def add_block(self, block_type: str, purpose: str, settings: dict = None):
        self.additional_blocks.append(
            AdditionalBlock(
                block_type=block_type,
                purpose=purpose,
                suggested_settings=settings or {},
            )
        )

    def calculate_confidence(self) -> float:
        """Calculate overall translation confidence."""
        if not self.approximations:
            return 1.0

        confidence_weights = {
            MappingConfidence.DIRECT: 1.0,
            MappingConfidence.APPROXIMATE: 0.7,
            MappingConfidence.ESTIMATED: 0.4,
            MappingConfidence.GAP: 0.0,
        }

        total_weight = sum(confidence_weights[a.confidence] for a in self.approximations)
        return total_weight / len(self.approximations)


def map_waveform(mxr_waveform: VoiceWaveform) -> Waveform:
    """Map MXR waveform to Axioma waveform."""
    mapping = {
        VoiceWaveform.TRIANGLE: Waveform.TRIANGLE,
        VoiceWaveform.SAWTOOTH: Waveform.SAW,
        VoiceWaveform.SQUARE: Waveform.SQUARE,
    }
    return mapping[mxr_waveform]


def map_tracking_mode(mxr_tracking: TrackingMode) -> InstrumentMode:
    """Map MXR tracking mode to Axioma instrument mode."""
    mapping = {
        TrackingMode.FIVE_STRING: InstrumentMode.FIVE_STRING,
        TrackingMode.FOUR_STRING: InstrumentMode.FOUR_STRING,
        TrackingMode.GUITAR: InstrumentMode.GUITAR,
    }
    return mapping[mxr_tracking]


def translate_mxr_to_axioma(mxr_preset: MXRPreset) -> AxiomaPreset:
    """Translate an MXR Bass Synth preset to Axioma.

    Args:
        mxr_preset: Source MXR preset

    Returns:
        Translated Axioma preset with full mapping report
    """
    report = MappingReport()

    primary_waveform = map_waveform(mxr_preset.switches.voice_waveform)
    report.add_approximation(
        source_param="voice_waveform",
        target_param="osc1_waveform",
        confidence=MappingConfidence.DIRECT,
        source_value={"triangle": 0, "sawtooth": 0.5, "square": 1}[
            mxr_preset.switches.voice_waveform.value
        ],
        target_value={"triangle": 0, "saw": 0.5, "square": 1}[primary_waveform.value],
        notes="Direct waveform mapping",
    )

    osc1_level = 1.0 - mxr_preset.voice.voice_mix
    osc2_level = mxr_preset.voice.voice_mix * 0.7
    report.add_approximation(
        source_param="voice_mix",
        target_param="osc1_level + osc2_level",
        confidence=MappingConfidence.APPROXIMATE,
        source_value=mxr_preset.voice.voice_mix,
        target_value=osc2_level,
        notes="MXR voice_mix maps to OSC1/OSC2 balance; "
        "MXR adds harmonics, Axioma uses independent oscillators",
    )

    sub_level = mxr_preset.primary.sub_mix
    report.add_approximation(
        source_param="sub_mix",
        target_param="sub_level",
        confidence=MappingConfidence.DIRECT,
        source_value=sub_level,
        target_value=sub_level,
        notes="Direct sub oscillator level mapping",
    )

    cutoff = mxr_preset.primary.cutoff
    report.add_approximation(
        source_param="cutoff",
        target_param="filter.cutoff",
        confidence=MappingConfidence.DIRECT,
        source_value=cutoff,
        target_value=cutoff,
        notes="Direct filter cutoff mapping",
    )

    resonance = mxr_preset.primary.resonance
    report.add_approximation(
        source_param="resonance",
        target_param="filter.resonance",
        confidence=MappingConfidence.DIRECT,
        source_value=resonance,
        target_value=resonance,
        notes="Direct filter resonance mapping",
    )

    env_amount = abs(mxr_preset.voice.filter_env_amount)
    report.add_approximation(
        source_param="filter_env_amount",
        target_param="filter.env_amount",
        confidence=MappingConfidence.APPROXIMATE,
        source_value=mxr_preset.voice.filter_env_amount,
        target_value=env_amount,
        notes="Axioma may not support negative envelope direction; using absolute value",
    )

    env_decay = mxr_preset.primary.envelope
    report.add_approximation(
        source_param="envelope",
        target_param="filter.env_decay",
        confidence=MappingConfidence.APPROXIMATE,
        source_value=env_decay,
        target_value=env_decay,
        notes="MXR envelope controls attack/decay together; mapped to Axioma decay only",
    )

    attack = mxr_preset.voice.amp_envelope
    report.add_approximation(
        source_param="amp_envelope",
        target_param="envelope.attack",
        confidence=MappingConfidence.DIRECT,
        source_value=attack,
        target_value=attack,
        notes="Direct attack time mapping",
    )

    release = max(0.2, mxr_preset.primary.envelope * 0.5)
    report.add_approximation(
        source_param="envelope (derived)",
        target_param="envelope.release",
        confidence=MappingConfidence.ESTIMATED,
        source_value=mxr_preset.primary.envelope,
        target_value=release,
        notes="Release estimated from MXR envelope setting",
    )

    blend = mxr_preset.primary.mix
    report.add_approximation(
        source_param="mix",
        target_param="mixer.blend",
        confidence=MappingConfidence.DIRECT,
        source_value=blend,
        target_value=blend,
        notes="Direct dry/wet mix mapping",
    )

    if mxr_preset.voice.glide > 0.05:
        report.add_gap(
            feature="Glide/Portamento",
            reason="Axioma does not support portamento/glide between notes",
            workaround=None,
        )

    if mxr_preset.primary.mod > 0.1 or abs(mxr_preset.voice.mod_blend - 0.5) > 0.1:
        report.add_gap(
            feature="LFO Modulation",
            reason="Axioma does not have built-in LFO for filter/chorus modulation",
            workaround="Add a separate Modulation block in the Anagram signal chain",
        )
        report.add_block(
            block_type="Chorus/Modulation",
            purpose="Approximate MXR modulation section",
            settings={
                "depth": mxr_preset.primary.mod,
                "rate": 0.5,
                "notes": "Adjust rate to taste; MXR uses internal LFO",
            },
        )

    if mxr_preset.voice.noise_mix > 0.05:
        report.add_gap(
            feature="Noise Generator",
            reason="Axioma does not include a noise oscillator",
            workaround="Consider using distortion or other effects to add noise/grit",
        )

    if mxr_preset.shape.compression > 0.2:
        report.add_block(
            block_type="Compressor",
            purpose="Approximate MXR compression section",
            settings={
                "threshold": -20 + (mxr_preset.shape.compression * -20),
                "ratio": 2.0 + (mxr_preset.shape.compression * 6),
                "attack": 10,
                "release": 100,
            },
        )

    oscillators = AxiomaOscillators(
        osc1_waveform=primary_waveform,
        osc1_level=osc1_level,
        osc2_waveform=primary_waveform,
        osc2_level=osc2_level,
        osc2_tune=0,
        osc2_detune=mxr_preset.voice.voice_mix * 15,
        sub_level=sub_level,
    )

    filter_section = AxiomaFilter(
        cutoff=cutoff,
        resonance=resonance,
        env_amount=env_amount,
        env_decay=env_decay,
    )

    envelope_section = AxiomaEnvelope(
        attack=attack,
        release=release,
    )

    mixer = AxiomaMixer(blend=blend)

    arpeggiator = AxiomaArpeggiator(enabled=False)

    instrument_mode = map_tracking_mode(mxr_preset.shape.tracking)

    translation_meta = TranslationMetadata(
        source_preset_id=mxr_preset.id,
        source_preset_name=mxr_preset.name,
        mapping_version="1.0",
        approximations=report.approximations,
        gaps=report.gaps,
        additional_blocks=report.additional_blocks,
        overall_confidence=report.calculate_confidence(),
    )

    axioma_preset = AxiomaPreset(
        id=str(uuid.uuid4()),
        name=f"{mxr_preset.name} (Axioma)",
        oscillators=oscillators,
        filter=filter_section,
        envelope=envelope_section,
        mixer=mixer,
        arpeggiator=arpeggiator,
        instrument_mode=instrument_mode,
        translation=translation_meta,
    )

    return axioma_preset


def apply_parameter_adjustment(
    preset: AxiomaPreset, param_path: str, value: float
) -> AxiomaPreset:
    """Apply a single parameter adjustment to an Axioma preset.

    Args:
        preset: Source preset to modify
        param_path: Dot-separated parameter path (e.g., "filter.cutoff")
        value: New value for the parameter

    Returns:
        New preset with adjusted parameter
    """
    preset_dict = preset.model_dump()
    parts = param_path.split(".")

    target = preset_dict
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value

    return AxiomaPreset(**preset_dict)


def get_optimization_bounds() -> list[tuple[float, float]]:
    """Get parameter bounds for optimization.

    Returns:
        List of (min, max) tuples for each optimizable parameter
    """
    return [
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
        (0.0, 1.0),
    ]


def vector_to_axioma_params(vector: list[float], base_preset: AxiomaPreset) -> AxiomaPreset:
    """Convert optimization vector back to Axioma preset.

    Args:
        vector: Parameter vector from optimizer
        base_preset: Base preset to use for non-optimized values

    Returns:
        Axioma preset with optimized parameters
    """
    waveform_map = {0: Waveform.SAW, 1: Waveform.SQUARE, 2: Waveform.TRIANGLE}

    def nearest_waveform(v: float) -> Waveform:
        if v < 0.33:
            return Waveform.SAW
        elif v < 0.67:
            return Waveform.SQUARE
        return Waveform.TRIANGLE

    preset_dict = base_preset.model_dump()

    preset_dict["oscillators"]["osc1_waveform"] = nearest_waveform(vector[0])
    preset_dict["oscillators"]["osc1_level"] = vector[1]
    preset_dict["oscillators"]["osc2_waveform"] = nearest_waveform(vector[2])
    preset_dict["oscillators"]["osc2_level"] = vector[3]
    preset_dict["oscillators"]["osc2_tune"] = int((vector[4] * 48) - 24)
    preset_dict["oscillators"]["osc2_detune"] = (vector[5] * 200) - 100
    preset_dict["oscillators"]["sub_level"] = vector[6]
    preset_dict["filter"]["cutoff"] = vector[7]
    preset_dict["filter"]["resonance"] = vector[8]
    preset_dict["filter"]["env_amount"] = vector[9]
    preset_dict["filter"]["env_decay"] = vector[10]
    preset_dict["envelope"]["attack"] = vector[11]
    preset_dict["envelope"]["release"] = vector[12]
    preset_dict["mixer"]["blend"] = vector[13]

    return AxiomaPreset(**preset_dict)
