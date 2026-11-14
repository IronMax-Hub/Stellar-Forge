"""Planet classes (build plan, Phase 5): ordered rules, the first match wins, so every planet gets
exactly one class. Radius never enters. The thresholds are Stellar-Forge choices, varied in the
sensitivity runs:

- F_ENV_GIANT = 0.5: the hydrogen-helium envelope outweighs everything else;
- F_ENV_ENVELOPE = 0.01: below the few-percent envelope that already doubles a small planet's
  radius (Owen & Wu 2017);
- M_SOLID_BREAK = 2 M⊕: Chen & Kipping's (2017) break between solid and Neptunian worlds;
- M_ICE_GIANT = 10 M⊕: keeps small icy planets out of the ice-giant class (Uranus and Neptune are
  about 15 and 17 M⊕).
"""

import numpy as np

F_ENV_GIANT = 0.5
F_ENV_ENVELOPE = 0.01
M_SOLID_BREAK = 2.0
M_ICE_GIANT = 10.0
CLASSES = ("gas giant", "ice giant", "sub-Neptune", "super-Earth", "terrestrial")


def classify(m_planet, f_env, ice_rich):
    """The class of each planet from its mass (M⊕), envelope fraction M_env/M_p and whether its
    core grew beyond the snow line (ice-rich). Arrays broadcast; returns class names."""
    m, f, ice = np.broadcast_arrays(np.asarray(m_planet, float), np.asarray(f_env, float),
                                    np.asarray(ice_rich, bool))
    if np.any((f < 0) | (f > 1)) or np.any(m <= 0):
        raise ValueError("envelope fractions must lie in 0-1 and masses be positive")
    envelope = (f >= F_ENV_ENVELOPE) & (f < F_ENV_GIANT)
    return np.select(
        [f >= F_ENV_GIANT,
         envelope & (m >= M_ICE_GIANT) & ice,
         envelope,
         (f < F_ENV_ENVELOPE) & (m >= M_SOLID_BREAK)],
        CLASSES[:4], default=CLASSES[4])
