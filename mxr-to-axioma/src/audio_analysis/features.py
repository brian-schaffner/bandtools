"""Audio feature extraction for preset comparison."""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import librosa

from ..config import settings


@dataclass
class AudioFeatures:
    """Extracted audio features for comparison."""

    rms_envelope: np.ndarray = field(default_factory=lambda: np.array([]))
    spectral_centroid: np.ndarray = field(default_factory=lambda: np.array([]))
    spectral_bandwidth: np.ndarray = field(default_factory=lambda: np.array([]))
    spectral_rolloff: np.ndarray = field(default_factory=lambda: np.array([]))
    mfcc: np.ndarray = field(default_factory=lambda: np.array([]))
    chroma: np.ndarray = field(default_factory=lambda: np.array([]))
    zero_crossing_rate: np.ndarray = field(default_factory=lambda: np.array([]))

    log_spectrum: np.ndarray = field(default_factory=lambda: np.array([]))
    harmonic_spectrum: np.ndarray = field(default_factory=lambda: np.array([]))
    percussive_spectrum: np.ndarray = field(default_factory=lambda: np.array([]))

    onset_strength: np.ndarray = field(default_factory=lambda: np.array([]))
    onset_times: np.ndarray = field(default_factory=lambda: np.array([]))

    fundamental_freq: float = 0.0
    harmonic_ratio: float = 0.0

    sample_rate: int = 48000
    hop_length: int = 1024
    n_fft: int = 4096

    def get_summary(self) -> dict:
        """Get summary statistics of features."""
        return {
            "rms_mean": float(np.mean(self.rms_envelope)) if len(self.rms_envelope) > 0 else 0,
            "rms_std": float(np.std(self.rms_envelope)) if len(self.rms_envelope) > 0 else 0,
            "centroid_mean": (
                float(np.mean(self.spectral_centroid)) if len(self.spectral_centroid) > 0 else 0
            ),
            "centroid_std": (
                float(np.std(self.spectral_centroid)) if len(self.spectral_centroid) > 0 else 0
            ),
            "bandwidth_mean": (
                float(np.mean(self.spectral_bandwidth)) if len(self.spectral_bandwidth) > 0 else 0
            ),
            "rolloff_mean": (
                float(np.mean(self.spectral_rolloff)) if len(self.spectral_rolloff) > 0 else 0
            ),
            "zcr_mean": (
                float(np.mean(self.zero_crossing_rate))
                if len(self.zero_crossing_rate) > 0
                else 0
            ),
            "fundamental_freq": self.fundamental_freq,
            "harmonic_ratio": self.harmonic_ratio,
            "onset_count": len(self.onset_times),
        }


def extract_features(
    samples: np.ndarray,
    sample_rate: int,
    n_fft: Optional[int] = None,
    hop_length: Optional[int] = None,
) -> AudioFeatures:
    """Extract audio features for comparison.

    Args:
        samples: Audio samples (mono)
        sample_rate: Sample rate
        n_fft: FFT size (default from settings)
        hop_length: Hop length (default from settings)

    Returns:
        AudioFeatures with extracted features
    """
    n_fft = n_fft or settings.analysis_fft_size
    hop_length = hop_length or settings.analysis_hop_size

    samples = samples.astype(np.float32)

    rms = librosa.feature.rms(y=samples, frame_length=n_fft, hop_length=hop_length)[0]

    stft = librosa.stft(samples, n_fft=n_fft, hop_length=hop_length)
    magnitude = np.abs(stft)
    log_spectrum = librosa.amplitude_to_db(magnitude, ref=np.max)

    centroid = librosa.feature.spectral_centroid(
        y=samples, sr=sample_rate, n_fft=n_fft, hop_length=hop_length
    )[0]

    bandwidth = librosa.feature.spectral_bandwidth(
        y=samples, sr=sample_rate, n_fft=n_fft, hop_length=hop_length
    )[0]

    rolloff = librosa.feature.spectral_rolloff(
        y=samples, sr=sample_rate, n_fft=n_fft, hop_length=hop_length, roll_percent=0.85
    )[0]

    mfcc = librosa.feature.mfcc(
        y=samples, sr=sample_rate, n_mfcc=13, n_fft=n_fft, hop_length=hop_length
    )

    chroma = librosa.feature.chroma_stft(
        y=samples, sr=sample_rate, n_fft=n_fft, hop_length=hop_length
    )

    zcr = librosa.feature.zero_crossing_rate(y=samples, frame_length=n_fft, hop_length=hop_length)[
        0
    ]

    harmonic, percussive = librosa.effects.hpss(samples)
    harmonic_stft = librosa.stft(harmonic, n_fft=n_fft, hop_length=hop_length)
    percussive_stft = librosa.stft(percussive, n_fft=n_fft, hop_length=hop_length)
    harmonic_spectrum = librosa.amplitude_to_db(np.abs(harmonic_stft), ref=np.max)
    percussive_spectrum = librosa.amplitude_to_db(np.abs(percussive_stft), ref=np.max)

    onset_env = librosa.onset.onset_strength(y=samples, sr=sample_rate, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(
        y=samples, sr=sample_rate, hop_length=hop_length, onset_envelope=onset_env
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sample_rate, hop_length=hop_length)

    f0, _, _ = librosa.pyin(
        samples,
        fmin=librosa.note_to_hz("E1"),
        fmax=librosa.note_to_hz("C5"),
        sr=sample_rate,
        hop_length=hop_length,
    )
    valid_f0 = f0[~np.isnan(f0)]
    fundamental = float(np.median(valid_f0)) if len(valid_f0) > 0 else 0.0

    harmonic_energy = np.sum(np.abs(harmonic) ** 2)
    percussive_energy = np.sum(np.abs(percussive) ** 2)
    total_energy = harmonic_energy + percussive_energy
    h_ratio = harmonic_energy / total_energy if total_energy > 0 else 0.5

    return AudioFeatures(
        rms_envelope=rms,
        spectral_centroid=centroid,
        spectral_bandwidth=bandwidth,
        spectral_rolloff=rolloff,
        mfcc=mfcc,
        chroma=chroma,
        zero_crossing_rate=zcr,
        log_spectrum=log_spectrum,
        harmonic_spectrum=harmonic_spectrum,
        percussive_spectrum=percussive_spectrum,
        onset_strength=onset_env,
        onset_times=onset_times,
        fundamental_freq=fundamental,
        harmonic_ratio=h_ratio,
        sample_rate=sample_rate,
        hop_length=hop_length,
        n_fft=n_fft,
    )


def extract_filter_characteristics(
    dry_samples: np.ndarray,
    wet_samples: np.ndarray,
    sample_rate: int,
    n_fft: int = 4096,
) -> dict:
    """Estimate filter characteristics by comparing dry and wet signals.

    Args:
        dry_samples: Dry/DI signal
        wet_samples: Processed signal
        sample_rate: Sample rate
        n_fft: FFT size

    Returns:
        Dictionary with estimated filter parameters
    """
    min_len = min(len(dry_samples), len(wet_samples))
    dry = dry_samples[:min_len]
    wet = wet_samples[:min_len]

    dry_stft = librosa.stft(dry, n_fft=n_fft)
    wet_stft = librosa.stft(wet, n_fft=n_fft)

    epsilon = 1e-10
    transfer_function = np.abs(wet_stft) / (np.abs(dry_stft) + epsilon)
    avg_transfer = np.mean(transfer_function, axis=1)

    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)

    peak_idx = np.argmax(avg_transfer[1:]) + 1
    resonance_freq = freqs[peak_idx]

    cutoff_threshold = np.max(avg_transfer) * 0.707
    cutoff_candidates = np.where(avg_transfer > cutoff_threshold)[0]
    if len(cutoff_candidates) > 0:
        cutoff_idx = cutoff_candidates[-1]
        cutoff_freq = freqs[cutoff_idx]
    else:
        cutoff_freq = sample_rate / 4

    resonance_amount = avg_transfer[peak_idx] / np.mean(avg_transfer) if np.mean(avg_transfer) > 0 else 1.0

    return {
        "estimated_cutoff_hz": float(cutoff_freq),
        "estimated_resonance_freq_hz": float(resonance_freq),
        "resonance_amount": float(min(1.0, (resonance_amount - 1.0) / 5.0)),
        "transfer_function": avg_transfer,
        "frequencies": freqs,
    }


def extract_envelope_characteristics(
    samples: np.ndarray,
    sample_rate: int,
    hop_length: int = 512,
) -> dict:
    """Extract amplitude envelope characteristics.

    Args:
        samples: Audio samples
        sample_rate: Sample rate
        hop_length: Analysis hop length

    Returns:
        Dictionary with envelope parameters
    """
    rms = librosa.feature.rms(y=samples, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sample_rate, hop_length=hop_length)

    onset_frames = librosa.onset.onset_detect(y=samples, sr=sample_rate, hop_length=hop_length)

    attack_times = []
    decay_times = []

    for onset in onset_frames:
        if onset >= len(rms) - 1:
            continue

        peak_window_end = min(onset + int(0.5 * sample_rate / hop_length), len(rms))
        peak_idx = onset + np.argmax(rms[onset:peak_window_end])
        peak_val = rms[peak_idx]

        threshold_90 = peak_val * 0.9
        threshold_10 = peak_val * 0.1

        attack_start = onset
        for i in range(onset, -1, -1):
            if rms[i] < threshold_10:
                attack_start = i
                break

        attack_end = peak_idx
        for i in range(onset, peak_idx + 1):
            if rms[i] >= threshold_90:
                attack_end = i
                break

        attack_time = times[attack_end] - times[attack_start]
        attack_times.append(attack_time)

        decay_end = min(peak_idx + int(2.0 * sample_rate / hop_length), len(rms) - 1)
        decay_target_idx = decay_end
        for i in range(peak_idx, decay_end):
            if rms[i] < threshold_10:
                decay_target_idx = i
                break

        decay_time = times[decay_target_idx] - times[peak_idx]
        decay_times.append(decay_time)

    avg_attack = float(np.mean(attack_times)) if attack_times else 0.01
    avg_decay = float(np.mean(decay_times)) if decay_times else 0.1

    return {
        "attack_time_seconds": avg_attack,
        "decay_time_seconds": avg_decay,
        "attack_normalized": min(1.0, avg_attack / 0.5),
        "decay_normalized": min(1.0, avg_decay / 2.0),
        "onset_count": len(onset_frames),
    }
