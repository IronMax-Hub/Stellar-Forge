"""Core growth and gas capture (Ida & Lin 2004a, sections 2-3).

Masses in M⊕, times in years, distances in AU, Σ in g/cm². Equation numbers are Ida & Lin 2004a's.
"""

import numpy as np

KH_B, KH_C = 9.0, 3.0      # τ_KH = 10^b (M_p/M⊕)^-c yr, the paper's adopted b and c (eq. 34)
ALPHA_DEFAULT = 1e-3        # viscosity parameter (Ida & Lin 2008a, §3.4)


def isolation_mass(sigma_d, a_au, m_star_msun=1.0, spacing_hill=10.0):
    """M_c,iso ≃ 0.16 (Σ_d/10)^3/2 (a/1 AU)³ (Δa/10 r_H)^3/2 (M★/M☉)^-1/2 M⊕ (eq. 20): the core
    has swept its feeding zone, Δa = 10 Hill radii wide (Kokubo & Ida 1998)."""
    return (0.16 * (np.asarray(sigma_d) / 10.0) ** 1.5 * np.asarray(a_au) ** 3
            * (spacing_hill / 10.0) ** 1.5 * np.asarray(m_star_msun) ** -0.5)


def critical_core_mass(mdot_core_mearth_yr):
    """M_c,crit ≃ 10 (Ṁ_c / 10⁻⁶ M⊕ yr⁻¹)^1/4 M⊕ (eq. 33, from Ikoma et al. 2000): above it the
    envelope can no longer stay in hydrostatic balance and gas accretion starts."""
    return 10.0 * (np.maximum(np.asarray(mdot_core_mearth_yr), 0.0) / 1e-6) ** 0.25


def kelvin_helmholtz_time_yr(m_planet):
    """τ_KH ≃ 10⁹ (M_p/M⊕)⁻³ yr (eq. 34); the envelope grows as dM_p,g/dt = M_p / τ_KH."""
    return 10.0**KH_B * np.asarray(m_planet) ** -KH_C
