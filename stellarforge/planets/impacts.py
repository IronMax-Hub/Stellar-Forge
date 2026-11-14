"""After the gas: giant impacts among embryos (multiplicity version 2).

Two published prescriptions, one per scale:

- inside each seed's annulus (a seed stands for all the oligarchs there), the embryos merge by
  Ida & Lin 2004a's post-gas growth: dM_e/dt = M_e / τ_e,acc (eq. 24) up to the embryo isolation
  mass, eq. 20 with the feeding zone widened to Δa = V_surf / Ω_K (eq. 25);
- between seeds, orbits cross and the bodies merge on Zhou et al. 2007's crossing time, as Ida &
  Lin 2010 (Appendix, eqs. 15-20) use it.

Masses in M⊕, distances in AU, times in years. Bulk densities are 3 g/cm³ inside the snow line and
1 g/cm³ outside (Ida & Lin 2010, Appendix step 3).
"""

import numpy as np

from . import M_EARTH_PER_MSUN

G_CGS = 6.674e-8
AU_CM = 1.495978707e13
G_PER_MEARTH = 5.9722e27
YR_S = 3.15576e7
RHO_ROCK, RHO_ICE = 3.0, 1.0      # g/cm³


def bulk_density(a_au, a_ice_au):
    return np.where(np.asarray(a_au) > a_ice_au, RHO_ICE, RHO_ROCK)


def embryo_accretion_time_yr(m_embryo, a_au, f_d, eta, rho, m_star_msun=1.0):
    """τ_e,acc ≃ 4 × 10⁷ η_ice⁻¹ f_d⁻¹ (a/1 AU)³ (M_e/M⊕)^1/3 (ρ_e/1 g cm⁻³)^2/3 (M★/M☉)^1/2 yr
    (Ida & Lin 2004a, eq. 24): growth by giant impacts once the gas no longer damps eccentricities."""
    return (4e7 / (np.asarray(eta) * np.asarray(f_d)) * np.asarray(a_au) ** 3
            * np.asarray(m_embryo) ** (1 / 3) * np.asarray(rho) ** (2 / 3)
            * np.sqrt(m_star_msun))


def embryo_isolation_mass(sigma_d, a_au, rho, m_star_msun=1.0):
    """The embryo isolation mass: eq. 20 of Ida & Lin 2004a, M = 2π a Σ_d Δa, with the feeding zone
    widened to Δa = V_surf / Ω_K, V_surf = (G M / R)^1/2 and R = (3M / 4πρ)^1/3, solved for M.

    The paper's closed form (eq. 25) prints the density factor as (ρ_d/1 g cm⁻³)², with ρ_d its
    symbol for the disk's spatial solid density; this definition gives the embryo's own density
    to the power 1/4. The definition is used: at 1 AU with f_d = η = 1 it gives 0.32 M⊕ for ρ = 1
    (0.42 M⊕ for ρ = 3), against eq. 25's printed 0.52 M⊕. Taking V_surf as the escape speed
    (2GM/R)^1/2 instead would give 0.54 M⊕, which may be how 0.52 arose."""
    a_cm = np.asarray(a_au) * AU_CM
    omega = np.sqrt(G_CGS * np.asarray(m_star_msun) * M_EARTH_PER_MSUN * G_PER_MEARTH / a_cm**3)
    k = 2 * np.pi * a_cm * np.asarray(sigma_d) * np.sqrt(G_CGS) \
        * (4 * np.pi * np.asarray(rho) / 3) ** (1 / 6) / omega
    return k**1.5 / G_PER_MEARTH


def crossing_time_yr(m_i, m_j, a_i, a_j, e_i, e_j, m_star_msun=1.0):
    """Orbit-crossing time of a pair (Zhou et al. 2007, as Ida & Lin 2010 eqs. 15-16):
    log10(τ_cross / T_K) = A + B log10(b / 2.3 r_H), A = -2 + e0 - 0.27 log10 μ,
    B = 18.7 + 1.1 log10 μ - (16.8 + 1.2 log10 μ) e0, e0 = (e_i + e_j) a / 2b,
    μ = (m_i + m_j) / 2M★, r_H = ((m_i + m_j) / 3M★)^1/3 a, at the pair's mean a = √(a_i a_j)."""
    m_star = np.asarray(m_star_msun) * M_EARTH_PER_MSUN
    a = np.sqrt(np.asarray(a_i) * np.asarray(a_j))
    b = np.abs(np.asarray(a_j) - np.asarray(a_i))
    r_h = ((np.asarray(m_i) + np.asarray(m_j)) / (3 * m_star)) ** (1 / 3) * a
    log_mu = np.log10((np.asarray(m_i) + np.asarray(m_j)) / (2 * m_star))
    e0 = 0.5 * (np.asarray(e_i) + np.asarray(e_j)) * a / np.maximum(b, 1e-30)
    big_a = -2 + e0 - 0.27 * log_mu
    big_b = 18.7 + 1.1 * log_mu - (16.8 + 1.2 * log_mu) * e0
    t_k = a**1.5 / np.sqrt(m_star_msun)
    with np.errstate(over="ignore"):
        return t_k * 10.0 ** (big_a + big_b * np.log10(np.maximum(b, 1e-30) / (2.3 * r_h)))


def escape_eccentricity(m_pair, a_au, rho, m_star_msun=1.0):
    """e_esc = v_esc / v_K ≃ 0.28 ((m_i + m_j)/M⊕)^1/3 (ρ/3 g cm⁻³)^1/6 (a/1 AU)^1/2 (Ida & Lin
    2010, eq. 17); the (M★/M☉)^-1/2 follows from v_K ∝ M★^1/2 in its definition."""
    return (0.28 * np.asarray(m_pair) ** (1 / 3) * (np.asarray(rho) / 3) ** (1 / 6)
            * np.sqrt(a_au) / np.sqrt(m_star_msun))


def merged_orbit(m_k, m_l, a_k, a_l, e_k, e_l, theta):
    """The merged body's orbit (Ida & Lin 2010, eqs. 19-20): orbital energy conserved,
    (m_k + m_l)/a_kl = m_k/a_k + m_l/a_l, and the mass-weighted Laplace-Runge-Lenz vector conserved,
    with θ the angle between the two periastra at the collision."""
    m = m_k + m_l
    a = m / (m_k / a_k + m_l / a_l)
    ex = m_k * e_k + m_l * e_l * np.cos(theta)
    ey = m_l * e_l * np.sin(theta)
    return a, np.hypot(ex, ey) / m
