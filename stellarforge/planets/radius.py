"""Display radii from mass: Chen & Kipping's (2017, ApJ 834, 17) broken power law, ported from Aion
Forge's `frontend/src/simulation/planetBasics.ts` (MASS_RADIUS) and checked against the paper's
Table 1. Radii never enter the classification; they are for drawing and for radius-based surveys.

Terran up to 2.04 M⊕ (R = 1.008 M^0.279), Neptunian up to 0.414 M_J (index 0.589) and Jovian
beyond (index -0.044). Table 1 gives the first constant; the others follow from the segments
meeting at the transitions. The fit includes hot, inflated giants, so it puts a Saturn-mass planet
about a quarter larger than Saturn.
"""

import numpy as np

# (upper mass in M⊕, constant, index)
SEGMENTS = ((2.04, 1.008, 0.279), (131.6, 0.808, 0.589), (np.inf, 17.74, -0.044))


def radius_rearth(mass_mearth):
    """Mean radius (R⊕) for a mass (M⊕); the fit's ±spread is not drawn."""
    m = np.asarray(mass_mearth, float)
    if np.any(m <= 0):
        raise ValueError("masses must be positive")
    return np.select([m <= hi for hi, _, _ in SEGMENTS], [c * m**s for _, c, s in SEGMENTS])
