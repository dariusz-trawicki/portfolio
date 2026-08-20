"""
Feature extraction from a bearing vibration signal:
- 8 time-domain features
- 4 frequency-domain features (on the FFT spectrum of the raw signal)
- 4 Hilbert envelope-spectrum features (amplitude at BPFO/BPFI/BSF/FTF)

This same module is used by `feature_consumer` (Kafka streaming) and by the
training tasks in Airflow - a single source of truth for feature-extraction
logic.
"""
from __future__ import annotations
import numpy as np
from scipy import stats
from scipy.signal import hilbert, welch

from bearing_physics import DEFAULT_GEOMETRY, characteristic_frequencies

FEATURE_NAMES = [
    # time-domain (8)
    "t_mean", "t_std", "t_rms", "t_kurtosis", "t_skewness",
    "t_peak_to_peak", "t_crest_factor", "t_shape_factor",
    # frequency-domain (4)
    "f_dominant_freq", "f_spectral_centroid", "f_spectral_energy", "f_spectral_entropy",
    # envelope spectrum (4)
    "env_amp_bpfo", "env_amp_bpfi", "env_amp_bsf", "env_amp_ftf",
]


def _time_domain_features(x: np.ndarray) -> dict:
    rms = float(np.sqrt(np.mean(x ** 2)))
    mean_abs = float(np.mean(np.abs(x))) or 1e-12
    peak = float(np.max(np.abs(x)))
    return {
        "t_mean": float(np.mean(x)),
        "t_std": float(np.std(x)),
        "t_rms": rms,
        "t_kurtosis": float(stats.kurtosis(x)),
        "t_skewness": float(stats.skew(x)),
        "t_peak_to_peak": float(np.ptp(x)),
        "t_crest_factor": peak / (rms or 1e-12),
        "t_shape_factor": rms / mean_abs,
    }


def _freq_domain_features(x: np.ndarray, fs: int) -> dict:
    freqs, psd = welch(x, fs=fs, nperseg=min(2048, len(x)))
    psd_norm = psd / (np.sum(psd) + 1e-12)
    dominant_freq = float(freqs[np.argmax(psd)])
    centroid = float(np.sum(freqs * psd_norm))
    energy = float(np.sum(psd))
    entropy = float(-np.sum(psd_norm * np.log2(psd_norm + 1e-12)))
    return {
        "f_dominant_freq": dominant_freq,
        "f_spectral_centroid": centroid,
        "f_spectral_energy": energy,
        "f_spectral_entropy": entropy,
    }


def _envelope_spectrum_features(x: np.ndarray, fs: int, shaft_hz: float,
                                 tolerance_hz: float = 3.0) -> dict:
    envelope = np.abs(hilbert(x))
    envelope = envelope - np.mean(envelope)
    spectrum = np.abs(np.fft.rfft(envelope))
    freqs = np.fft.rfftfreq(len(envelope), d=1.0 / fs)

    char_freqs = characteristic_frequencies(shaft_hz, DEFAULT_GEOMETRY)
    out = {}
    for key, target_freq in char_freqs.items():
        mask = (freqs >= target_freq - tolerance_hz) & (freqs <= target_freq + tolerance_hz)
        out[f"env_amp_{key.lower()}"] = float(np.max(spectrum[mask])) if np.any(mask) else 0.0
    return out


def extract_features(signal: np.ndarray, fs: int, shaft_rpm: float) -> dict:
    """Returns a dict {feature_name: value} matching FEATURE_NAMES."""
    x = np.asarray(signal, dtype=float)
    shaft_hz = shaft_rpm / 60.0

    feats = {}
    feats.update(_time_domain_features(x))
    feats.update(_freq_domain_features(x, fs))
    feats.update(_envelope_spectrum_features(x, fs, shaft_hz))
    return feats
