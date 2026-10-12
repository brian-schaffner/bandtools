"""Audio file loading utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from ..config import settings


@dataclass
class AudioFile:
    """Loaded audio file with metadata."""

    path: Path
    samples: np.ndarray
    sample_rate: int
    channels: int
    duration_seconds: float

    @property
    def is_mono(self) -> bool:
        return self.channels == 1

    @property
    def is_stereo(self) -> bool:
        return self.channels == 2


def load_audio(
    path: Path | str,
    target_sr: Optional[int] = None,
    mono: bool = True,
) -> AudioFile:
    """Load an audio file.

    Args:
        path: Path to audio file
        target_sr: Target sample rate (None to keep original)
        mono: Whether to convert to mono

    Returns:
        AudioFile with loaded samples and metadata

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is unsupported
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in settings.supported_audio_formats:
        raise ValueError(
            f"Unsupported audio format: {suffix}. "
            f"Supported: {settings.supported_audio_formats}"
        )

    samples, sample_rate = sf.read(path, always_2d=True)

    if mono and samples.shape[1] > 1:
        samples = np.mean(samples, axis=1, keepdims=True)

    channels = samples.shape[1]

    if mono:
        samples = samples.flatten()

    if target_sr and target_sr != sample_rate:
        import librosa

        if mono:
            samples = librosa.resample(samples, orig_sr=sample_rate, target_sr=target_sr)
        else:
            resampled = []
            for ch in range(channels):
                ch_samples = librosa.resample(
                    samples[:, ch], orig_sr=sample_rate, target_sr=target_sr
                )
                resampled.append(ch_samples)
            samples = np.column_stack(resampled)
        sample_rate = target_sr

    duration = len(samples) / sample_rate if mono else samples.shape[0] / sample_rate

    return AudioFile(
        path=path,
        samples=samples,
        sample_rate=sample_rate,
        channels=1 if mono else channels,
        duration_seconds=duration,
    )


def save_audio(
    path: Path | str,
    samples: np.ndarray,
    sample_rate: int,
) -> None:
    """Save audio to file.

    Args:
        path: Output path
        samples: Audio samples
        sample_rate: Sample rate
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, samples, sample_rate)


def normalize_audio(samples: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Normalize audio to target peak level.

    Args:
        samples: Input samples
        target_peak: Target peak level (0-1)

    Returns:
        Normalized samples
    """
    peak = np.max(np.abs(samples))
    if peak > 0:
        return samples * (target_peak / peak)
    return samples


def align_audio(
    reference: np.ndarray,
    target: np.ndarray,
    sample_rate: int,
    max_shift_ms: float = 100,
) -> tuple[np.ndarray, int]:
    """Align target audio to reference using cross-correlation.

    Args:
        reference: Reference audio samples
        target: Target audio to align
        sample_rate: Sample rate
        max_shift_ms: Maximum shift to search in milliseconds

    Returns:
        Tuple of (aligned target samples, shift in samples)
    """
    max_shift_samples = int(max_shift_ms * sample_rate / 1000)

    min_len = min(len(reference), len(target))
    ref_segment = reference[:min_len]
    tgt_segment = target[:min_len]

    correlation = np.correlate(ref_segment, tgt_segment, mode="full")
    center = len(correlation) // 2

    search_start = max(0, center - max_shift_samples)
    search_end = min(len(correlation), center + max_shift_samples)

    peak_idx = search_start + np.argmax(correlation[search_start:search_end])
    shift = peak_idx - center

    if shift > 0:
        aligned = np.concatenate([np.zeros(shift), target[:-shift] if shift < len(target) else []])
    elif shift < 0:
        aligned = target[-shift:]
    else:
        aligned = target

    return aligned, shift


def trim_silence(
    samples: np.ndarray,
    sample_rate: int,
    threshold_db: float = -60,
    min_silence_ms: float = 100,
) -> np.ndarray:
    """Trim silence from beginning and end of audio.

    Args:
        samples: Input samples
        sample_rate: Sample rate
        threshold_db: Silence threshold in dB
        min_silence_ms: Minimum silence duration to trim

    Returns:
        Trimmed samples
    """
    threshold_linear = 10 ** (threshold_db / 20)
    min_silence_samples = int(min_silence_ms * sample_rate / 1000)

    abs_samples = np.abs(samples)

    above_threshold = abs_samples > threshold_linear

    if not np.any(above_threshold):
        return samples

    start_idx = 0
    for i in range(len(above_threshold)):
        if above_threshold[i]:
            start_idx = max(0, i - min_silence_samples)
            break

    end_idx = len(samples)
    for i in range(len(above_threshold) - 1, -1, -1):
        if above_threshold[i]:
            end_idx = min(len(samples), i + min_silence_samples)
            break

    return samples[start_idx:end_idx]
