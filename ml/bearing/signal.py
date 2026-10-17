"""Shared validation, windowing, and engineered vibration features."""
from __future__ import annotations

import math
import numpy as np

FEATURE_VERSION = "axon-vibration-features-v1"


def validate_signal(signal, sampling_frequency_hz: float, *, minimum_samples: int = 16) -> np.ndarray:
    values = np.asarray(signal, dtype=np.float64).reshape(-1)
    if not np.isfinite(sampling_frequency_hz) or sampling_frequency_hz <= 0:
        raise ValueError("sampling_frequency_hz must be a finite positive value")
    if values.size < minimum_samples:
        raise ValueError(f"signal must have at least {minimum_samples} samples")
    if not np.isfinite(values).all():
        raise ValueError("signal contains non-finite values")
    return values


def segment_signal(signal, sampling_frequency_hz: float, window_samples: int, overlap_samples: int) -> list[np.ndarray]:
    values = validate_signal(signal, sampling_frequency_hz, minimum_samples=window_samples)
    if not 0 <= overlap_samples < window_samples:
        raise ValueError("overlap_samples must be non-negative and smaller than window_samples")
    stride = window_samples - overlap_samples
    return [values[offset : offset + window_samples] for offset in range(0, len(values) - window_samples + 1, stride)]


def _spectral_entropy(power: np.ndarray) -> float:
    total = float(power.sum())
    if total <= 0:
        return 0.0
    probabilities = power / total
    probabilities = probabilities[probabilities > 0]
    return float(-(probabilities * np.log2(probabilities)).sum() / math.log2(max(len(power), 2)))


def feature_names() -> tuple[str, ...]:
    return ("mean", "std", "rms", "variance", "peak_amplitude", "peak_to_peak", "crest_factor", "skewness", "kurtosis", "energy", "frequency_energy", "dominant_frequency_hz", "spectral_centroid_hz", "spectral_entropy", "low_band_energy", "high_band_energy")


def engineered_features(window, sampling_frequency_hz: float) -> dict[str, float]:
    values = validate_signal(window, sampling_frequency_hz)
    centered = values - values.mean()
    rms = float(np.sqrt(np.mean(values ** 2)))
    std = float(values.std())
    peak = float(np.max(np.abs(values)))
    if std == 0:
        skewness = kurtosis = 0.0
    else:
        normalized = centered / std
        skewness = float(np.mean(normalized ** 3))
        kurtosis = float(np.mean(normalized ** 4) - 3.0)
    spectrum = np.fft.rfft(centered)
    power = np.abs(spectrum) ** 2
    frequencies = np.fft.rfftfreq(len(values), d=1.0 / sampling_frequency_hz)
    non_dc = power.copy()
    if non_dc.size:
        non_dc[0] = 0
    dominant = float(frequencies[int(np.argmax(non_dc))]) if non_dc.any() else 0.0
    total_power = float(power.sum())
    centroid = float(np.dot(frequencies, power) / total_power) if total_power else 0.0
    split = max(1, len(power) // 4)
    result = {
        "mean": float(values.mean()), "std": std, "rms": rms, "variance": float(values.var()),
        "peak_amplitude": peak, "peak_to_peak": float(values.max() - values.min()),
        "crest_factor": peak / rms if rms else 0.0, "skewness": skewness, "kurtosis": kurtosis,
        "energy": float(np.sum(values ** 2)), "frequency_energy": total_power,
        "dominant_frequency_hz": dominant, "spectral_centroid_hz": centroid,
        "spectral_entropy": _spectral_entropy(power), "low_band_energy": float(power[:split].sum()),
        "high_band_energy": float(power[split:].sum()),
    }
    if not all(np.isfinite(value) for value in result.values()):
        raise ValueError("feature extraction produced non-finite values")
    return result


def feature_vector(window, sampling_frequency_hz: float) -> np.ndarray:
    features = engineered_features(window, sampling_frequency_hz)
    return np.asarray([features[name] for name in feature_names()], dtype=np.float64)
