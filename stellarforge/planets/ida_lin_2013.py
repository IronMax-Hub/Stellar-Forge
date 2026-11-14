"""The gas-phase prescriptions of Ida, Lin & Nagasawa 2013 (ApJ 775, 42; arXiv:1307.6450; "Paper
VII"), which revise Ida & Lin 2004a's: a steady-accretion gas disk, core growth with Paper IV's typos
corrected, gas accretion limited by the disk's own accretion rate and tapered by gap opening, and
type II migration in disk- and planet-dominated regimes. Equation numbers are Paper VII's.

Masses in M⊕, distances in AU, times in years. L★ = (M★/M☉)⁴, as Ida & Lin 2008a §3.3 assume.
"""

import numpy as np

from . import M_EARTH_PER_MSUN

SIGMA_G10 = 75.0              # g/cm² at 10 AU for f_g = 1 (eq. 15)
ALPHA = 1e-3                  # §3.1
C2 = 0.1                      # type II torque asymmetry, the paper's adopted value (§3.5)
AU_CM = 1.495978707e13
G_PER_MEARTH = 5.9722e27


def luminosity_lsun(m_star_msun):
    return np.asarray(m_star_msun) ** 4


def sigma_gas(a_au, f_g):
    """Σ_g = 75 f_g (r / 10 AU)⁻¹ g/cm² (eq. 15): a steady α disk, scaled to the MMSN at 10 AU."""
    return SIGMA_G10 * np.asarray(f_g) * (np.asarray(a_au) / 10.0) ** -1


def core_accretion_time_yr(m_core, a_au, f_d, f_g, eta, m_star_msun=1.0):
    """τ_c,acc = 3.5 × 10⁵ η_ice⁻¹ f_d⁻¹ f_g^-2/5 (a/1 AU)^5/2 (M_c/M⊕)^1/3 (M★/M☉)^-1/6 yr
    (eq. 19)."""
    return (3.5e5 / (np.asarray(eta) * np.asarray(f_d)) * np.asarray(f_g) ** -0.4
            * np.asarray(a_au) ** 2.5 * np.asarray(m_core) ** (1 / 3)
            * np.asarray(m_star_msun) ** (-1 / 6))


def type1_rate(a_au, m_planet, f_g, m_star_msun=1.0, c1=0.1):
    """da/dt = -a / τ_mig1, τ_mig1 ≃ 1.5 × 10⁵ C1⁻¹ f_g⁻¹ (M_p/M⊕)⁻¹ (a/1 AU) (M★/M☉)^3/2 yr
    (eq. 22, Tanaka et al. 2002 scaled by C1)."""
    a = np.asarray(a_au)
    tau = 1.5e5 / (c1 * np.asarray(f_g)) / np.asarray(m_planet) * a \
        * np.asarray(m_star_msun) ** 1.5
    return -a / tau


def disk_accretion_rate(f_g, alpha=ALPHA):
    """Ṁ_disk ≃ 3π Σ_g ν ≃ 3 × 10⁻⁹ f_g (α/10⁻³) M☉/yr (eq. 26), here in M⊕/yr."""
    return 3e-9 * np.asarray(f_g) * (alpha / 1e-3) * M_EARTH_PER_MSUN


def viscous_gap_mass(a_au, m_star_msun=1.0, alpha=ALPHA):
    """M_g,vis ≃ 30 (α/10⁻³) (a/1 AU)^1/2 (L★/L☉)^1/4 M⊕ (eq. 27): a partial gap opens and type II
    migration begins."""
    return 30.0 * (alpha / 1e-3) * np.sqrt(a_au) * luminosity_lsun(m_star_msun) ** 0.25


def thermal_gap_mass(a_au, m_star_msun=1.0):
    """M_g,th ≃ 0.95 × 10³ (a/1 AU)^3/4 (L★/L☉)^3/8 (M★/M☉)^-1/2 M⊕ (eq. 28): the Hill radius reaches
    twice the scale height and gas accretion ends."""
    return (0.95e3 * np.asarray(a_au) ** 0.75 * luminosity_lsun(m_star_msun) ** 0.375
            / np.sqrt(m_star_msun))


def gap_factor(m_planet, a_au, m_star_msun=1.0, alpha=ALPHA):
    """f_gap (eq. 31): 1 below M_g,vis, falling linearly in log M to 0 at M_g,th."""
    lo = np.log(viscous_gap_mass(a_au, m_star_msun, alpha))
    hi = np.log(thermal_gap_mass(a_au, m_star_msun))
    return np.clip((hi - np.log(np.maximum(m_planet, 1e-30))) / (hi - lo), 0.0, 1.0)


def viscous_couple_radius_au(t_yr, tau_dep_yr, m_star_msun=1.0, alpha=ALPHA):
    """r_m, the radius of maximum viscous couple, which Paper VII uses (§3.5) but does not give.

    At t = 0 it follows from eqs. 32-33: for T of eq. 16, ν ∝ r and τ_dep ≈ 2 r_m² / 3ν(r_m) =
    0.7 × 10⁵ (α/10⁻³)⁻¹ (r_m/1 AU) (M★/M☉)^-1/2 yr, so r_m,0 = (τ_dep / 7 × 10⁴ yr) (α/10⁻³)
    (M★/M☉)^1/2 AU, the paper's 15-150 AU for 1-10 Myr. It then grows as the disk spreads. Ida & Lin
    2004a's argument (eqs. 66-67, total angular momentum conserved, J ∝ Σ_g,10 r_m^3/2 for Σ_g ∝ r⁻¹)
    gives r_m ∝ Σ_g^-2/3, so r_m = r_m,0 exp(2t / 3τ_dep) under eq. 18's decay."""
    r0 = np.asarray(tau_dep_yr) / 7e4 * (alpha / 1e-3) * np.sqrt(m_star_msun)
    return r0 * np.exp(2 * np.asarray(t_yr) / (3 * np.asarray(tau_dep_yr)))


def disk_mass_mearth(f_g, r_m_au):
    """Gas inside r_m for eq. 15's profile, ∫ 2π r Σ_g dr = 2π Σ_g,10 (10 AU) r_m, in M⊕: the test
    between the disk- and planet-dominated regimes of §3.5."""
    return 2 * np.pi * SIGMA_G10 * np.asarray(f_g) * (10 * AU_CM) * (np.asarray(r_m_au) * AU_CM) \
        / G_PER_MEARTH


def type2_rate(a_au, m_planet, f_g, r_m_au, m_star_msun=1.0, alpha=ALPHA, c2=C2):
    """Type II migration (§3.5), inward inside r_m and outward beyond it. While the disk outweighs
    the planet, τ = 0.7 × 10⁵ (α/10⁻³)⁻¹ (a/1 AU) (M★/M☉)^-1/2 yr (eq. 32); after that, the
    planet-dominated τ = (1/2C2) (a/r_m)^1/2 M_p / Ṁ_disk (eq. 34's definition)."""
    a, m = np.asarray(a_au), np.asarray(m_planet)
    disk = 0.7e5 / (alpha / 1e-3) * a / np.sqrt(m_star_msun)
    planet = 0.5 / c2 * np.sqrt(a / np.asarray(r_m_au)) * m / disk_accretion_rate(f_g, alpha)
    tau = np.where(disk_mass_mearth(f_g, r_m_au) > m, disk, planet)
    return np.where(a < r_m_au, -1.0, 1.0) * a / tau

