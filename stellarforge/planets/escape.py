"""Energy-limited escape of hydrogen-helium envelopes (Owen & Wu 2017, new code, not a port).

- Rate (eq. 19): Ṁ_env = η π R_p³ L_HE / (4π a² G M_p), η = 0.1, with L_HE the star's XUV
  (xuv.py) along its track.
- Radius: the core from eq. 15 (M_c ∝ R_c⁴, ρ_M⊕ = 5.5 g/cm³, Earth-like) and the envelope from
  eq. 14 normalised at X₂, the envelope fraction X = M_env / M_c that doubles the core's radius
  (eq. 17): X ∝ (ΔR/R_c)^1.57 below ΔR = R_c and (ΔR/R_c)^1.31 above (eq. 16 at γ = 5/3 and
  Rogers & Seager's 2010 opacity law, α = 0.68, β = 0.45). τ_KH is the planet's age.

Limits: the model holds for X < 1 (the envelope's self-gravity is ignored), so planets with more
gas than core take the Chen & Kipping radius (radius.py), flagged. The isothermal layer above the
radiative-convective boundary is not added (R_p ≈ R_rcb), which Owen & Wu correct for.
"""

import numpy as np

from .radius import radius_rearth as chen_kipping_radius

ETA = 0.1
N_THIN, N_THICK = 1.57, 1.31      # eq. 16: n_a, n_b
RHO_M_EARTH = 5.5                 # g/cm³, Earth-like core (eq. 15)
G_CGS = 6.674e-8
M_EARTH_G = 5.9722e27
R_EARTH_CM = 6.371e8
AU_CM = 1.495978707e13
L_SUN_ERG_S = 3.828e33
YEAR_S = 3.15576e7


def x2(period_days, m_star_msun, age_yr, core_mearth, rho_m_earth=RHO_M_EARTH):
    """Eq. 17: the envelope fraction X = M_env/M_c at which the radius doubles."""
    return (0.027 * (np.asarray(period_days) / 10) ** 0.08 * np.asarray(m_star_msun) ** -0.15
            * (np.maximum(age_yr, 1e6) / 1e8) ** 0.37 * (rho_m_earth / 5.5) ** -0.82
            * (np.asarray(core_mearth) / 5) ** 0.17)


def radius_rearth(core_mearth, env_mearth, period_days, m_star_msun, age_yr):
    """Planet radius (R⊕) and whether Owen & Wu's thin-envelope model applies (X < 1)."""
    core = np.asarray(core_mearth, float)
    x = np.asarray(env_mearth, float) / core
    s = x / x2(period_days, m_star_msun, age_yr, core)
    dr = np.where(s < 1, s ** (1 / N_THIN), s ** (1 / N_THICK))
    valid = x < 1
    owen_wu = core**0.25 * (1 + dr)
    return np.where(valid, owen_wu, chen_kipping_radius(core + env_mearth)), valid


def mass_loss_g_s(radius_rearth_, mass_mearth, a_au, l_xuv_lsun):
    """Eq. 19 in g/s."""
    r = np.asarray(radius_rearth_) * R_EARTH_CM
    return (ETA * np.pi * r**3 * np.asarray(l_xuv_lsun) * L_SUN_ERG_S
            / (4 * np.pi * (np.asarray(a_au) * AU_CM) ** 2 * G_CGS
               * np.asarray(mass_mearth) * M_EARTH_G))


def mass_loss_mearth_yr(radius_rearth_, mass_mearth, a_au, l_xuv_lsun):
    return mass_loss_g_s(radius_rearth_, mass_mearth, a_au, l_xuv_lsun) * YEAR_S / M_EARTH_G
