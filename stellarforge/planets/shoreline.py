"""The cosmic shoreline as a kept-or-lost atmosphere label, ported from Aion Forge's
`frontend/src/simulation/atmosphericEscape.ts` (criticalDose, airRetained; see PROVENANCE.md).

In the Solar System, bodies with and without air divide along cumulative XUV dose ∝ v_esc⁴
(Zahnle & Catling 2017): an observed trend, not a mass-loss rate. The dose is counted in Earth
doses (the MIST Sun's XUV fluence at 1 AU over its first 4.6 Gyr = 1). A world keeps a share
r = max(0, 1 - (X / X_crit)²) of its air, X_crit = K (v_esc / 11.2 km/s)⁴. The v_esc⁴ slope is
Zahnle & Catling's; K = 10 (placed between Titan and Mars) and the retention curve are Aion
Forge's choices and are labelled as such. Energy-limited escape (escape.py) is kept apart.
"""

import numpy as np

ESCAPE_K = 10.0                 # Aion Forge's choice
EARTH_ESCAPE_VELOCITY_KMS = 11.2


def critical_dose(v_esc_kms):
    """The dose (Earth doses) a world with this escape velocity can hold out against."""
    return ESCAPE_K * (np.asarray(v_esc_kms, float) / EARTH_ESCAPE_VELOCITY_KMS) ** 4


def air_retained(dose, v_esc_kms):
    """The share of its air a world keeps after a dose (Aion Forge's retention curve)."""
    x = np.asarray(dose, float) / critical_dose(v_esc_kms)
    return np.maximum(0.0, 1 - x * x)
