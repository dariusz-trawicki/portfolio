"""
Synthetic vibration signal generator simulating a train wheel bearing in
operation. Extended vs. the earlier demo version with a fourth fault class:
`cage` (cage/retainer, FTF frequency) - see "known simplifications" in the
session summary.
"""
from __future__ import annotations
import numpy as np

from bearing_physics import DEFAULT_GEOMETRY, FAULT_TO_FREQ_KEY, characteristic_frequencies


def _impulse_train(t: np.ndarray, fault_freq_hz: float, resonance_hz: float,
                    decay: float, amplitude: float, rng: np.random.Generator,
                    jitter: float = 0.01) -> np.ndarray:
    """Simulates a train of impact impulses (fault signature) modulated by
    housing resonance - the classic signal model for a damaged bearing."""
    if fault_freq_hz <= 0:
        return np.zeros_like(t)
    period = 1.0 / fault_freq_hz
    duration = t[-1] - t[0]
    n_impulses = int(duration / period) + 2
    signal = np.zeros_like(t)
    for i in range(n_impulses):
        # small time jitter - realistic slip, not perfectly periodic
        t0 = i * period + rng.normal(0, jitter * period)
        envelope = amplitude * np.exp(-decay * np.clip(t - t0, 0, None)) * (t >= t0)
        signal += envelope * np.sin(2 * np.pi * resonance_hz * (t - t0))
    return signal


def generate_signal(fault_type: str, shaft_rpm: float, duration_s: float = 1.0,
                     fs: int = 20000, noise_std: float = 0.15,
                     seed: int | None = None) -> np.ndarray:
    """Generates a single time-domain waveform [g] for the given fault type
    and shaft speed (RPM)."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, duration_s, 1.0 / fs)
    shaft_hz = shaft_rpm / 60.0

    # baseline noise + shaft-speed harmonic (imbalance etc.)
    signal = rng.normal(0, noise_std, size=t.shape)
    signal += 0.05 * np.sin(2 * np.pi * shaft_hz * t)

    if fault_type == "normal":
        return signal

    freqs = characteristic_frequencies(shaft_hz, DEFAULT_GEOMETRY)
    freq_key = FAULT_TO_FREQ_KEY.get(fault_type)
    if freq_key is None:
        raise ValueError(f"Unknown fault type: {fault_type}")

    fault_freq = freqs[freq_key]
    resonance_hz = fs / 8.0  # typical housing/sensor resonance frequency
    signal += _impulse_train(t, fault_freq, resonance_hz, decay=800.0,
                              amplitude=1.0, rng=rng)
    return signal


def random_shaft_rpm(rng: np.random.Generator, base_rpm: float = 1780.0,
                      spread_rpm: float = 40.0) -> float:
    """Random shaft speed - simulates variable operating conditions."""
    return float(base_rpm + rng.normal(0, spread_rpm))
