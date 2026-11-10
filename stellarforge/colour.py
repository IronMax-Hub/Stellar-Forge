"""A star's display colour from its effective temperature: Tanner Helland's blackbody fit.

Ported from Aion Forge `frontend/src/simulation/star.ts`, `temperatureToColor` (read in place; see
PROVENANCE.md) with its coefficients unchanged. A standard display approximation of a blackbody's
colour, not a spectrum calculation. Temperatures are clamped to 1,000-40,000 K.
"""

import numpy as np

HOT_RED = 329.698727446 / 255
HOT_GREEN = 288.1221695283 / 255


def temperature_to_rgb(teff_k) -> np.ndarray:
    """sRGB, 0-1 per channel, shape (..., 3)."""
    t = np.clip(np.asarray(teff_k, dtype=float), 1000, 40000) / 100
    hot = t > 66
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(hot, (t - 60) ** -0.1332 * HOT_RED, 1.0)
        g = np.where(hot, (t - 60) ** -0.0755 * HOT_GREEN, np.log(t) * 0.3909 - 0.5516)
        b = np.where(t >= 66, 1.0, np.where(t <= 19, 0.0, np.log(t - 10) * 0.5432 - 1.196))
    return np.clip(np.stack([r, g, b], axis=-1), 0, 1)
