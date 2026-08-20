"""
Bearing geometry parameters and formulas for the characteristic fault
frequencies (BPFO, BPFI, BSF, FTF).

Default parameters correspond to a typical deep-groove ball bearing (roughly
in line with bearings used in public datasets such as the CWRU Bearing Data
Center) - n=9 balls, ~0 degree contact angle.
"""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BearingGeometry:
    n_balls: int = 9
    ball_diameter_mm: float = 7.94
    pitch_diameter_mm: float = 39.04
    contact_angle_deg: float = 0.0

    @property
    def d_over_D(self) -> float:
        return self.ball_diameter_mm / self.pitch_diameter_mm

    @property
    def cos_phi(self) -> float:
        return math.cos(math.radians(self.contact_angle_deg))


DEFAULT_GEOMETRY = BearingGeometry()


def characteristic_frequencies(shaft_hz: float, geom: BearingGeometry = DEFAULT_GEOMETRY) -> dict:
    """Returns a dict of characteristic frequencies [Hz] for the given shaft
    speed (shaft_hz = revolutions/second)."""
    n = geom.n_balls
    k = geom.d_over_D * geom.cos_phi

    bpfo = (n / 2.0) * shaft_hz * (1 - k)
    bpfi = (n / 2.0) * shaft_hz * (1 + k)
    bsf = (geom.pitch_diameter_mm / (2 * geom.ball_diameter_mm)) * shaft_hz * (1 - k ** 2)
    ftf = (shaft_hz / 2.0) * (1 - k)

    return {"BPFO": bpfo, "BPFI": bpfi, "BSF": bsf, "FTF": ftf}


FAULT_TYPES = ("normal", "outer", "inner", "ball", "cage")
# Maps fault type -> the characteristic-frequency key that the
# generator/detector should excite / look for in the envelope spectrum.
FAULT_TO_FREQ_KEY = {
    "outer": "BPFO",
    "inner": "BPFI",
    "ball": "BSF",
    "cage": "FTF",
}
