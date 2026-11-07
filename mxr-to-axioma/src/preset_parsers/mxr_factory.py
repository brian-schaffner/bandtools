"""MXR Bass Synth factory preset definitions.

These presets are based on the factory preset descriptions from the MXR MB301 manual.
Parameter values are estimates derived from the documented sonic characteristics.
"""

from __future__ import annotations

from typing import Optional
import uuid

from .mxr_preset import (
    MXRPreset,
    MXRPrimaryParams,
    MXRVoiceParams,
    MXRShapeParams,
    MXRSwitchStates,
    MXRPresetMetadata,
    VoiceWaveform,
    TrackingMode,
    OutputMode,
    PresetSource,
)


MXR_FACTORY_PRESETS: dict[str, dict] = {
    "THRILLENGANES": {
        "description": "Michael Jackson 'Thriller' - octave-down ARP 2600 style",
        "primary": MXRPrimaryParams(
            mix=0.85,
            sub_mix=0.7,
            cutoff=0.45,
            resonance=0.3,
            envelope=0.4,
            mod=0.1,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.3,
            noise_mix=0.0,
            filter_env_amount=0.4,
            glide=0.05,
            amp_envelope=0.1,
            mod_blend=0.5,
        ),
        "shape": MXRShapeParams(
            compression=0.4,
            output_gain=0.0,
            gate_sensitivity=0.5,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=False,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SAWTOOTH,
            bypass=False,
        ),
    },
    "WONDERFUL": {
        "description": "Stevie Wonder TONTO synth - short funky resonant drops",
        "primary": MXRPrimaryParams(
            mix=0.9,
            sub_mix=0.4,
            cutoff=0.6,
            resonance=0.55,
            envelope=0.25,
            mod=0.05,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.5,
            noise_mix=0.0,
            filter_env_amount=0.6,
            glide=0.0,
            amp_envelope=0.05,
            mod_blend=0.5,
        ),
        "shape": MXRShapeParams(
            compression=0.3,
            output_gain=0.0,
            gate_sensitivity=0.6,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=False,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SQUARE,
            bypass=False,
        ),
    },
    "LIZARD SYNTH": {
        "description": "Herbie Hancock 'Chameleon' - ARP Odyssey style resonant funk",
        "primary": MXRPrimaryParams(
            mix=0.8,
            sub_mix=0.35,
            cutoff=0.5,
            resonance=0.7,
            envelope=0.5,
            mod=0.15,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.6,
            noise_mix=0.0,
            filter_env_amount=0.7,
            glide=0.1,
            amp_envelope=0.1,
            mod_blend=0.4,
        ),
        "shape": MXRShapeParams(
            compression=0.25,
            output_gain=0.0,
            gate_sensitivity=0.5,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=False,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SAWTOOTH,
            bypass=False,
        ),
    },
    "SYNTHADELIC": {
        "description": "Parliament 'Flashlight' Minimoog - wide open octave-down",
        "primary": MXRPrimaryParams(
            mix=0.95,
            sub_mix=0.8,
            cutoff=0.7,
            resonance=0.25,
            envelope=0.35,
            mod=0.2,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.4,
            noise_mix=0.0,
            filter_env_amount=0.3,
            glide=0.15,
            amp_envelope=0.15,
            mod_blend=0.6,
        ),
        "shape": MXRShapeParams(
            compression=0.35,
            output_gain=3.0,
            gate_sensitivity=0.4,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=False,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SQUARE,
            bypass=False,
        ),
    },
    "SLEDGE": {
        "description": "Peter Gabriel 'Sledgehammer' - analog octave with chorus + compression",
        "primary": MXRPrimaryParams(
            mix=0.75,
            sub_mix=0.6,
            cutoff=0.55,
            resonance=0.2,
            envelope=0.3,
            mod=0.45,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.5,
            noise_mix=0.0,
            filter_env_amount=0.35,
            glide=0.0,
            amp_envelope=0.05,
            mod_blend=0.7,
        ),
        "shape": MXRShapeParams(
            compression=0.6,
            output_gain=0.0,
            gate_sensitivity=0.5,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=True,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SAWTOOTH,
            bypass=False,
        ),
    },
    "ARMY OF SYNTH": {
        "description": "Björk 'Army of Me' - expression pedal recommended",
        "primary": MXRPrimaryParams(
            mix=0.9,
            sub_mix=0.5,
            cutoff=0.3,
            resonance=0.5,
            envelope=0.6,
            mod=0.25,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.45,
            noise_mix=0.05,
            filter_env_amount=0.8,
            glide=0.0,
            amp_envelope=0.2,
            mod_blend=0.35,
        ),
        "shape": MXRShapeParams(
            compression=0.5,
            output_gain=2.0,
            gate_sensitivity=0.55,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=False,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SQUARE,
            bypass=False,
        ),
    },
    "NINE INCH SYNTH": {
        "description": "NIN 'Head Like a Hole' - aggressive industrial synth bass",
        "primary": MXRPrimaryParams(
            mix=1.0,
            sub_mix=0.45,
            cutoff=0.4,
            resonance=0.45,
            envelope=0.55,
            mod=0.3,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.7,
            noise_mix=0.1,
            filter_env_amount=0.65,
            glide=0.0,
            amp_envelope=0.05,
            mod_blend=0.25,
        ),
        "shape": MXRShapeParams(
            compression=0.7,
            output_gain=4.0,
            gate_sensitivity=0.6,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=False,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SAWTOOTH,
            bypass=False,
        ),
    },
    "SYNTHMAU5": {
        "description": "EDM sidechain pumping style - play with quarter note bass drum",
        "primary": MXRPrimaryParams(
            mix=0.85,
            sub_mix=0.55,
            cutoff=0.35,
            resonance=0.35,
            envelope=0.7,
            mod=0.4,
        ),
        "voice": MXRVoiceParams(
            voice_mix=0.55,
            noise_mix=0.0,
            filter_env_amount=-0.5,
            glide=0.0,
            amp_envelope=0.3,
            mod_blend=0.5,
        ),
        "shape": MXRShapeParams(
            compression=0.8,
            output_gain=0.0,
            gate_sensitivity=0.7,
            tracking=TrackingMode.FIVE_STRING,
            dry_thru_fx=False,
            output_mode=OutputMode.MONO,
        ),
        "switches": MXRSwitchStates(
            voice_waveform=VoiceWaveform.SQUARE,
            bypass=False,
        ),
    },
}


def get_factory_preset(name: str) -> Optional[MXRPreset]:
    """Get a factory preset by name.

    Args:
        name: Factory preset name (case-insensitive)

    Returns:
        MXRPreset if found, None otherwise
    """
    name_upper = name.upper()
    if name_upper not in MXR_FACTORY_PRESETS:
        return None

    preset_data = MXR_FACTORY_PRESETS[name_upper]
    return MXRPreset(
        id=str(uuid.uuid4()),
        name=name_upper,
        primary=preset_data["primary"],
        voice=preset_data["voice"],
        shape=preset_data["shape"],
        switches=preset_data["switches"],
        metadata=MXRPresetMetadata(
            source=PresetSource.FACTORY,
            confidence=0.8,
            notes=preset_data["description"],
            factory_name=name_upper,
        ),
    )


def list_factory_presets() -> list[dict]:
    """List all available factory presets with descriptions."""
    return [
        {"name": name, "description": data["description"]}
        for name, data in MXR_FACTORY_PRESETS.items()
    ]
