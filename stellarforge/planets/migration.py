"""Orbital migration in the gas disk.

Type II (gap-opening giants) follows Ida & Lin 2004a, section 5; type I (smaller planets) is
Tanaka et al. 2002's linear rate scaled by C1 (Ida & Lin 2008a, eqs. 4 and 12). Rates in AU/yr,
negative inward.
"""

import numpy as np

from . import M_EARTH_PER_MSUN, M_JUPITER_MEARTH
from .disk import aspect_ratio, sigma_gas

INNER_EDGE_AU = 0.04          # migration halts near the star (Ida & Lin 2004a, §5.1)
AU_CM = 1.495978707e13
C1_DEFAULT = 0.1              # type I reduction; 0.03-0.1 matches observations (Ida & Lin 2008a)


def max_viscous_couple_radius_au(t_yr, tau_disk_yr):
    """R_m = 10 exp(2t / 5τ_disk) AU (eq. 68): inside it the gas, and a gap-opening planet with it,
    drifts inwards; outside, outwards."""
    return 10.0 * np.exp(2 * np.asarray(t_yr) / (5 * np.asarray(tau_disk_yr)))


def type2_rate(a_au, m_planet, f_g, t_yr, tau_disk_yr, m_star_msun=1.0, alpha=1e-3):
    """da/dt = ±a / τ_mig with τ_mig = 0.8 × 10⁶ f_g⁻¹ (M_p/M_J)(M☉/M★)(α/10⁻⁴)⁻¹ (a/1 AU)^1/2 yr
    (eq. 65), never faster than the gas itself, τ_disk,acc = 4.3 × 10⁵ (α/10⁻⁴)⁻¹ (a/1 AU) yr
    (eq. 70). Inward inside R_m, outward beyond it."""
    a = np.asarray(a_au)
    tau = 0.8e6 / np.asarray(f_g) * (np.asarray(m_planet) / M_JUPITER_MEARTH) \
        / np.asarray(m_star_msun) * (alpha / 1e-4) ** -1 * a**0.5
    tau = np.maximum(tau, 4.3e5 * (alpha / 1e-4) ** -1 * a)
    sign = np.where(a < max_viscous_couple_radius_au(t_yr, tau_disk_yr), -1.0, 1.0)
    return sign * a / tau


def type1_rate(a_au, m_planet, f_g, m_star_msun=1.0, c1=C1_DEFAULT, p=-1.5, q=-0.5):
    """da/dt = C1 × 1.08 (p + 0.80 q - 2.52)(M_p/M★)(Σ_g a²/M★)(a Ω_K / c_s)² a Ω_K, with
    p = dlnΣ_g/dln a and q = dlnT/dln a (Tanaka et al. 2002, as Ida & Lin 2008a eqs. 4 and 12).
    For the disk of eq. 12 (p = -3/2) and eq. 14 (q = -1/2) the migration is inward."""
    a = np.asarray(a_au)
    m_star_g = np.asarray(m_star_msun) * 1.98841e33
    disk_mass_ratio = sigma_gas(a, f_g) * (a * AU_CM) ** 2 / m_star_g
    omega_yr = 2 * np.pi * np.sqrt(np.asarray(m_star_msun) / a**3)      # Kepler, per year
    mass_ratio = np.asarray(m_planet) / (np.asarray(m_star_msun) * M_EARTH_PER_MSUN)
    return (c1 * 1.08 * (p + 0.80 * q - 2.52) * mass_ratio * disk_mass_ratio
            * aspect_ratio(a) ** -2 * a * omega_yr)
