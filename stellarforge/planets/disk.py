"""The protoplanetary disk's solids, its gas depletion and the snow line (Ida & Lin 2004a, 2004b;
the gas profile itself is Paper VII's, in ida_lin_2013.py).

Equation numbers refer to Ida & Lin 2004a (ApJ 604, 388; arXiv:astro-ph/0312144) unless stated.
"""

import numpy as np

ETA_ICE = 4.2          # solids boost beyond the snow line (eq. 11; Hayashi 1981)
SIGMA_D0 = 10.0        # g/cm² at 1 AU for f_d = 1 (eq. 11)


def snow_line_au(m_star_msun):
    """a_ice = 2.7 (M★/M☉)² AU, from T = 170 K with L★ ∝ M★⁴ (eq. 15)."""
    return 2.7 * np.asarray(m_star_msun) ** 2


def snow_line_from_luminosity_au(l_star_lsun):
    """a_ice = 2.7 (L★/L☉)^1/2 AU: eq. 14 at 170 K, the plan's later upgrade (MIST luminosity)."""
    return 2.7 * np.sqrt(np.asarray(l_star_lsun))


def eta_ice(a_au, a_ice_au):
    """The step in eq. 11: 1 inside the snow line, 4.2 beyond it."""
    return np.where(np.asarray(a_au) > a_ice_au, ETA_ICE, 1.0)


def f_dust(f_gas, feh):
    """Solids scale with the star's metallicity: f_d = f_g 10^[Fe/H] (Ida & Lin 2004b, 2008a §3.3)."""
    return np.asarray(f_gas) * 10.0 ** np.asarray(feh)


def sigma_dust(a_au, f_d, a_ice_au):
    """Σ_d = 10 f_d η_ice (a/1 AU)^-3/2 g/cm² (eq. 11)."""
    a = np.asarray(a_au)
    return SIGMA_D0 * f_d * eta_ice(a, a_ice_au) * a**-1.5


def gas_factor(f_g0, t_yr, tau_disk_yr):
    """f_g = f_g0 exp(-t/τ_disk): the gas is depleted globally and self-similarly (eq. 49)."""
    return np.asarray(f_g0) * np.exp(-np.asarray(t_yr) / tau_disk_yr)
