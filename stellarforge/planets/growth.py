"""Core growth and gas capture (Ida & Lin 2004a, sections 2-3).

Masses in M⊕, times in years, distances in AU, Σ in g/cm². Equation numbers are Ida & Lin 2004a's.
"""

import numpy as np

KH_B, KH_C = 9.0, 3.0      # τ_KH = 10^b (M_p/M⊕)^-c yr, the paper's adopted b and c (eq. 34)
ALPHA_DEFAULT = 1e-3        # viscosity parameter (Ida & Lin 2008a, §3.4)


def core_accretion_time_yr(m_core, a_au, f_d, f_g, eta, m_star_msun=1.0):
    """τ_c,acc ≃ 1.2 × 10⁵ η_ice⁻¹ f_d⁻¹ f_g^-2/5 (a/1 AU)^27/10 (M_c/M⊕)^1/3 (M★/M☉)^-1/6 yr
    (eq. 18); the core grows as dM_c/dt = M_c / τ_c,acc (eq. 32)."""
    return (1.2e5 / (np.asarray(eta) * np.asarray(f_d)) * np.asarray(f_g) ** -0.4
            * np.asarray(a_au) ** 2.7 * np.asarray(m_core) ** (1 / 3)
            * np.asarray(m_star_msun) ** (-1 / 6))


def isolation_mass(sigma_d, a_au, m_star_msun=1.0, spacing_hill=10.0):
    """M_c,iso ≃ 0.16 (Σ_d/10)^3/2 (a/1 AU)³ (Δa/10 r_H)^3/2 (M★/M☉)^-1/2 M⊕ (eq. 20): the core
    has swept its feeding zone, Δa = 10 Hill radii wide (Kokubo & Ida 1998)."""
    return (0.16 * (np.asarray(sigma_d) / 10.0) ** 1.5 * np.asarray(a_au) ** 3
            * (spacing_hill / 10.0) ** 1.5 * np.asarray(m_star_msun) ** -0.5)


def no_isolation_mass(sigma_d, a_au):
    """M_c,noiso ≃ π a² Σ_d ≃ 1.2 (Σ_d/10)(a/1 AU)² M⊕ (eq. 22): a migrating core that gathers all
    the solids inside its orbit."""
    return 1.2 * np.asarray(sigma_d) / 10.0 * np.asarray(a_au) ** 2


def critical_core_mass(mdot_core_mearth_yr):
    """M_c,crit ≃ 10 (Ṁ_c / 10⁻⁶ M⊕ yr⁻¹)^1/4 M⊕ (eq. 33, from Ikoma et al. 2000): above it the
    envelope can no longer stay in hydrostatic balance and gas accretion starts."""
    return 10.0 * (np.maximum(np.asarray(mdot_core_mearth_yr), 0.0) / 1e-6) ** 0.25


def kelvin_helmholtz_time_yr(m_planet):
    """τ_KH ≃ 10⁹ (M_p/M⊕)⁻³ yr (eq. 34); the envelope grows as dM_p,g/dt = M_p / τ_KH."""
    return 10.0**KH_B * np.asarray(m_planet) ** -KH_C


def gas_isolation_mass(sigma_g, a_au, m_star_msun=1.0, spacing_hill=2.0):
    """M_g,iso ≃ 50 (Σ_g/2.4 × 10³)^3/2 (a/1 AU)³ (Δa_g/2 r_H)^3/2 (M★/M☉)^-1/2 M⊕ (eq. 35)."""
    return (50.0 * (np.asarray(sigma_g) / 2.4e3) ** 1.5 * np.asarray(a_au) ** 3
            * (spacing_hill / 2.0) ** 1.5 * np.asarray(m_star_msun) ** -0.5)


def gap_opening_mass(a_au, m_star_msun=1.0):
    """M_g,th ≃ 3.8 × 10⁻⁴ (a/1 AU)^3/4 M★ (≃ 120 (a/1 AU)^3/4 M⊕ for the Sun): the Hill radius
    reaches the disk scale height and the planet opens a gap, halting gas inflow (eq. 38)."""
    from . import M_EARTH_PER_MSUN
    return 3.8e-4 * np.asarray(a_au) ** 0.75 * np.asarray(m_star_msun) * M_EARTH_PER_MSUN


def disk_gas_mass_limit(f_g, a_au):
    """M_g,noiso ≃ π a² Σ_g ≃ 290 f_g (a/1 AU)^1/2 M⊕: all the gas left in the disk (eq. 47)."""
    return 290.0 * np.asarray(f_g) * np.asarray(a_au) ** 0.5
