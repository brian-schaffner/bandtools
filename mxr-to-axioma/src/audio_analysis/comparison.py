"""Audio comparison engine for optimization."""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy import signal
from scipy.spatial.distance import cosine

from .features import AudioFeatures, extract_features
from .loader import align_audio, normalize_audio


@dataclass
class AudioComparison:
    """Result of comparing two audio signals."""

    overall_similarity: float
    spectral_similarity: float
    envelope_similarity: float
    harmonic_similarity: float
    transient_similarity: float
    timbral_similarity: float
    dynamic_similarity: float

    spectral_difference_db: float
    centroid_difference_hz: float
    envelope_correlation: float

    details: dict

    def get_summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"Overall Similarity: {self.overall_similarity * 100:.1f}%\n"
            f"  Spectral: {self.spectral_similarity * 100:.1f}%\n"
            f"  Envelope: {self.envelope_similarity * 100:.1f}%\n"
            f"  Harmonic: {self.harmonic_similarity * 100:.1f}%\n"
            f"  Transient: {self.transient_similarity * 100:.1f}%\n"
            f"  Timbral: {self.timbral_similarity * 100:.1f}%\n"
            f"  Dynamic: {self.dynamic_similarity * 100:.1f}%"
        )


def compare_audio(
    reference_samples: np.ndarray,
    target_samples: np.ndarray,
    sample_rate: int,
    align: bool = True,
    normalize: bool = True,
    reference_features: Optional[AudioFeatures] = None,
    target_features: Optional[AudioFeatures] = None,
) -> AudioComparison:
    """Compare two audio signals and compute similarity metrics.

    Args:
        reference_samples: Reference audio (MXR output)
        target_samples: Target audio (Axioma output)
        sample_rate: Sample rate
        align: Whether to time-align signals
        normalize: Whether to loudness-normalize signals
        reference_features: Pre-computed features for reference
        target_features: Pre-computed features for target

    Returns:
        AudioComparison with detailed similarity metrics
    """
    if normalize:
        reference_samples = normalize_audio(reference_samples)
        target_samples = normalize_audio(target_samples)

    if align:
        target_samples, shift = align_audio(reference_samples, target_samples, sample_rate)

    min_len = min(len(reference_samples), len(target_samples))
    ref = reference_samples[:min_len]
    tgt = target_samples[:min_len]

    if reference_features is None:
        reference_features = extract_features(ref, sample_rate)
    if target_features is None:
        target_features = extract_features(tgt, sample_rate)

    spectral_sim = compute_spectral_similarity(reference_features, target_features)
    envelope_sim, env_corr = compute_envelope_similarity(reference_features, target_features)
    harmonic_sim = compute_harmonic_similarity(reference_features, target_features)
    transient_sim = compute_transient_similarity(reference_features, target_features)
    timbral_sim = compute_timbral_similarity(reference_features, target_features)
    dynamic_sim = compute_dynamic_similarity(ref, tgt, sample_rate)

    spectral_diff = compute_spectral_difference(reference_features, target_features)
    centroid_diff = abs(
        np.mean(reference_features.spectral_centroid) - np.mean(target_features.spectral_centroid)
    )

    weights = {
        "spectral": 0.25,
        "envelope": 0.15,
        "harmonic": 0.20,
        "transient": 0.10,
        "timbral": 0.20,
        "dynamic": 0.10,
    }

    overall = (
        weights["spectral"] * spectral_sim
        + weights["envelope"] * envelope_sim
        + weights["harmonic"] * harmonic_sim
        + weights["transient"] * transient_sim
        + weights["timbral"] * timbral_sim
        + weights["dynamic"] * dynamic_sim
    )

    return AudioComparison(
        overall_similarity=overall,
        spectral_similarity=spectral_sim,
        envelope_similarity=envelope_sim,
        harmonic_similarity=harmonic_sim,
        transient_similarity=transient_sim,
        timbral_similarity=timbral_sim,
        dynamic_similarity=dynamic_sim,
        spectral_difference_db=spectral_diff,
        centroid_difference_hz=centroid_diff,
        envelope_correlation=env_corr,
        details={
            "weights": weights,
            "reference_summary": reference_features.get_summary(),
            "target_summary": target_features.get_summary(),
        },
    )


def compute_spectral_similarity(ref: AudioFeatures, tgt: AudioFeatures) -> float:
    """Compute spectral similarity using log-frequency spectrum."""
    ref_spectrum = np.mean(ref.log_spectrum, axis=1)
    tgt_spectrum = np.mean(tgt.log_spectrum, axis=1)

    min_bins = min(len(ref_spectrum), len(tgt_spectrum))
    ref_spectrum = ref_spectrum[:min_bins]
    tgt_spectrum = tgt_spectrum[:min_bins]

    ref_norm = (ref_spectrum - np.mean(ref_spectrum)) / (np.std(ref_spectrum) + 1e-10)
    tgt_norm = (tgt_spectrum - np.mean(tgt_spectrum)) / (np.std(tgt_spectrum) + 1e-10)

    correlation = np.corrcoef(ref_norm, tgt_norm)[0, 1]

    similarity = (correlation + 1) / 2

    return float(max(0, min(1, similarity)))


def compute_envelope_similarity(ref: AudioFeatures, tgt: AudioFeatures) -> tuple[float, float]:
    """Compute amplitude envelope similarity."""
    ref_env = ref.rms_envelope
    tgt_env = tgt.rms_envelope

    min_len = min(len(ref_env), len(tgt_env))
    ref_env = ref_env[:min_len]
    tgt_env = tgt_env[:min_len]

    if len(ref_env) == 0 or len(tgt_env) == 0:
        return 0.5, 0.0

    correlation = np.corrcoef(ref_env, tgt_env)[0, 1]
    if np.isnan(correlation):
        correlation = 0.0

    ref_norm = ref_env / (np.max(ref_env) + 1e-10)
    tgt_norm = tgt_env / (np.max(tgt_env) + 1e-10)
    mse = np.mean((ref_norm - tgt_norm) ** 2)
    shape_similarity = 1 - np.sqrt(mse)

    similarity = 0.5 * ((correlation + 1) / 2) + 0.5 * max(0, shape_similarity)

    return float(max(0, min(1, similarity))), float(correlation)


def compute_harmonic_similarity(ref: AudioFeatures, tgt: AudioFeatures) -> float:
    """Compute similarity of harmonic content."""
    ref_harmonic = np.mean(ref.harmonic_spectrum, axis=1)
    tgt_harmonic = np.mean(tgt.harmonic_spectrum, axis=1)

    min_bins = min(len(ref_harmonic), len(tgt_harmonic))
    ref_harmonic = ref_harmonic[:min_bins]
    tgt_harmonic = tgt_harmonic[:min_bins]

    ref_norm = ref_harmonic / (np.linalg.norm(ref_harmonic) + 1e-10)
    tgt_norm = tgt_harmonic / (np.linalg.norm(tgt_harmonic) + 1e-10)
    cosine_sim = 1 - cosine(ref_norm, tgt_norm)

    hr_diff = abs(ref.harmonic_ratio - tgt.harmonic_ratio)
    hr_sim = 1 - hr_diff

    similarity = 0.7 * cosine_sim + 0.3 * hr_sim

    return float(max(0, min(1, similarity)))


def compute_transient_similarity(ref: AudioFeatures, tgt: AudioFeatures) -> float:
    """Compute similarity of transient/onset characteristics."""
    ref_onsets = len(ref.onset_times)
    tgt_onsets = len(tgt.onset_times)

    if ref_onsets == 0 and tgt_onsets == 0:
        return 1.0
    if ref_onsets == 0 or tgt_onsets == 0:
        return 0.5

    count_ratio = min(ref_onsets, tgt_onsets) / max(ref_onsets, tgt_onsets)

    ref_strength = ref.onset_strength
    tgt_strength = tgt.onset_strength

    min_len = min(len(ref_strength), len(tgt_strength))
    ref_strength = ref_strength[:min_len]
    tgt_strength = tgt_strength[:min_len]

    if len(ref_strength) > 0 and len(tgt_strength) > 0:
        correlation = np.corrcoef(ref_strength, tgt_strength)[0, 1]
        if np.isnan(correlation):
            correlation = 0.0
        strength_sim = (correlation + 1) / 2
    else:
        strength_sim = 0.5

    similarity = 0.4 * count_ratio + 0.6 * strength_sim

    return float(max(0, min(1, similarity)))


def compute_timbral_similarity(ref: AudioFeatures, tgt: AudioFeatures) -> float:
    """Compute timbral similarity using MFCCs."""
    ref_mfcc = np.mean(ref.mfcc, axis=1)
    tgt_mfcc = np.mean(tgt.mfcc, axis=1)

    min_coeffs = min(len(ref_mfcc), len(tgt_mfcc))
    ref_mfcc = ref_mfcc[:min_coeffs]
    tgt_mfcc = tgt_mfcc[:min_coeffs]

    euclidean_dist = np.linalg.norm(ref_mfcc - tgt_mfcc)
    max_dist = np.sqrt(min_coeffs) * 50
    similarity = 1 - min(1, euclidean_dist / max_dist)

    return float(max(0, min(1, similarity)))


def compute_dynamic_similarity(
    ref_samples: np.ndarray, tgt_samples: np.ndarray, sample_rate: int
) -> float:
    """Compute dynamic response similarity across different input levels."""
    window_size = int(0.1 * sample_rate)
    hop = window_size // 2

    ref_levels = []
    tgt_levels = []

    for i in range(0, min(len(ref_samples), len(tgt_samples)) - window_size, hop):
        ref_rms = np.sqrt(np.mean(ref_samples[i : i + window_size] ** 2))
        tgt_rms = np.sqrt(np.mean(tgt_samples[i : i + window_size] ** 2))
        if ref_rms > 0.01:
            ref_levels.append(ref_rms)
            tgt_levels.append(tgt_rms)

    if len(ref_levels) < 2:
        return 0.5

    ref_levels = np.array(ref_levels)
    tgt_levels = np.array(tgt_levels)

    correlation = np.corrcoef(ref_levels, tgt_levels)[0, 1]
    if np.isnan(correlation):
        correlation = 0.0

    ref_range = np.max(ref_levels) - np.min(ref_levels)
    tgt_range = np.max(tgt_levels) - np.min(tgt_levels)
    if max(ref_range, tgt_range) > 0:
        range_sim = min(ref_range, tgt_range) / max(ref_range, tgt_range)
    else:
        range_sim = 1.0

    similarity = 0.6 * ((correlation + 1) / 2) + 0.4 * range_sim

    return float(max(0, min(1, similarity)))


def compute_spectral_difference(ref: AudioFeatures, tgt: AudioFeatures) -> float:
    """Compute average spectral difference in dB."""
    ref_spectrum = np.mean(ref.log_spectrum, axis=1)
    tgt_spectrum = np.mean(tgt.log_spectrum, axis=1)

    min_bins = min(len(ref_spectrum), len(tgt_spectrum))
    ref_spectrum = ref_spectrum[:min_bins]
    tgt_spectrum = tgt_spectrum[:min_bins]

    diff_db = np.mean(np.abs(ref_spectrum - tgt_spectrum))

    return float(diff_db)


def compute_similarity_score(
    reference_samples: np.ndarray,
    target_samples: np.ndarray,
    sample_rate: int,
) -> float:
    """Compute a single similarity score for optimization.

    Args:
        reference_samples: Reference audio
        target_samples: Target audio
        sample_rate: Sample rate

    Returns:
        Similarity score between 0 and 1
    """
    comparison = compare_audio(reference_samples, target_samples, sample_rate)
    return comparison.overall_similarity
