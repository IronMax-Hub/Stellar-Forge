"""Survey checks (build plan, Phase 5 Validation): the model's planets seen through each survey's
own cuts, against the survey's published numbers. Surveys are observational constraints: they check
the model and never enter it.

Numbers are from the papers' abstracts (and `documentation/Source checks.md`):

- Fischer & Valenti 2005: giant-planet probability ∝ 10^(2.0 [Fe/H]) for FGK stars.
- Johnson et al. 2010: giant occurrence ∝ M★ × 10^(1.2 [Fe/H]); 3.5% at 0.5 M☉ to 14% at 2 M☉,
  solar [Fe/H].
- Cumming et al. 2008: 10.5% of solar-type stars have a planet of 0.3-10 M_J with P = 2-2,000 d;
  as in Johnson et al., radial-velocity masses are minimum masses, M sin i.
- Petigura et al. 2018: warm super-Earths (1.0-1.7 R⊕, P = 10-100 d) about 20 per 100 stars from
  [Fe/H] -0.4 to +0.4, slope β = -0.3 ± 0.2 in df ∝ 10^(β [Fe/H]); warm sub-Neptunes (1.7-4.0
  R⊕) double over the same range, 20 to 40 per 100 stars.

Tolerances are Stellar-Forge choices, stated with each check: the abstracts give few errors, and a
semi-analytic model is not expected to match to survey precision.
"""

import numpy as np

from . import M_JUPITER_MEARTH

GIANT_MASS_MEARTH = (0.3 * M_JUPITER_MEARTH, 10 * M_JUPITER_MEARTH)   # Cumming et al. 2008
GIANT_PERIOD_D = (2.0, 2000.0)
WARM_PERIOD_D = (10.0, 100.0)                                         # Petigura et al. 2018
SUPER_EARTH_R = (1.0, 1.7)
SUB_NEPTUNE_R = (1.7, 4.0)
DAYS_PER_YR = 365.25

FISCHER_VALENTI_BETA = 2.0
JOHNSON_BETA, JOHNSON_ALPHA = 1.2, 1.0
JOHNSON_AT = {0.5: 0.035, 2.0: 0.14}
CUMMING_SHARE = 0.105
PETIGURA_SE_PER_100, PETIGURA_SE_BETA, PETIGURA_SE_BETA_ERR = 20.0, -0.3, 0.2
PETIGURA_SN_PER_100 = (20.0, 40.0)        # at [Fe/H] -0.4 and +0.4

# Tolerances (Stellar-Forge choices)
BETA_GIANT_RANGE = (JOHNSON_BETA - 0.4, FISCHER_VALENTI_BETA + 0.4)   # the two surveys, ±0.4
ALPHA_RANGE = (0.5, 1.5)                    # Johnson's linear scaling, ±0.5
TWIN_FACTOR = 1.5                           # solar twin within a factor 1.5 of 10.5%
SE_LEVEL_FACTOR = 2.0                       # warm super-Earths within a factor 2 of 20 per 100
SE_BETA_SIGMA = 2.0                         # slope within 2σ of Petigura's


def period_days(a_au, m_star_msun):
    """Kepler's third law with the planet's mass neglected: P = a^3/2 / M★^1/2 years."""
    return DAYS_PER_YR * np.asarray(a_au) ** 1.5 / np.sqrt(m_star_msun)


def survey_stats(planets: dict, n_systems: int, m_star_msun: float, sin_i=None,
                 seed: int = 0) -> dict:
    """The cell's planets through each survey's cuts: the share of systems with an RV giant (by
    minimum mass M sin i, any composition, as a survey sees it; and counting only gas giants), and
    warm super-Earths and sub-Neptunes per 100 stars (radii from Chen & Kipping). Orbits are
    oriented at random (cos i uniform) unless sin_i is given."""
    p = period_days(planets["a_au"], m_star_msun)
    if sin_i is None:
        sin_i = np.sqrt(1 - np.random.default_rng(seed).uniform(0, 1, len(p)) ** 2)
    m, r = planets["mass_mearth"] * sin_i, planets["radius_rearth"]

    def inside(v, bounds):
        return (v >= bounds[0]) & (v <= bounds[1])
    giant = inside(m, GIANT_MASS_MEARTH) & inside(p, GIANT_PERIOD_D)
    warm = inside(p, WARM_PERIOD_D)
    enveloped = giant & (planets["f_env"] >= 0.5)
    return {"rv_giant_share": np.unique(planets["system"][giant]).size / n_systems,
            "rv_giant_share_gas_giants": np.unique(planets["system"][enveloped]).size / n_systems,
            "warm_super_earths_per_100": 100 * np.sum(warm & (r >= SUPER_EARTH_R[0])
                                                      & (r < SUPER_EARTH_R[1])) / n_systems,
            "warm_sub_neptunes_per_100": 100 * np.sum(warm & (r >= SUB_NEPTUNE_R[0])
                                                      & (r <= SUB_NEPTUNE_R[1])) / n_systems}


def slope(x, y) -> float:
    """Least-squares slope of log10 y against x; nan if any y is 0 (no planets to fit) or there
    are fewer than two points."""
    y = np.asarray(y, float)
    if len(y) < 2 or np.any(y <= 0):
        return float("nan")
    return float(np.polyfit(np.asarray(x, float), np.log10(y), 1)[0])
