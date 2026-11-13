"""Stellar structure from first principles (build plan, Phase 4).

Part A: polytropes. The Lane-Emden equation (Chandrasekhar 1939, chapter IV)

    (1/xi^2) d/dxi (xi^2 dtheta/dxi) = -theta^n,   theta(0) = 1, theta'(0) = 0,

is solved with SciPy for any index 0 <= n <= 5. Density is rho = rho_c theta^n and pressure
P = K rho^(1 + 1/n). The cases n = 0, 1 and 5 have exact solutions, which the tests compare against.
Applied to the Sun, n = 3 is Eddington's standard model; its central temperature is 1.21e7 K against
1.571e7 K in full solar models, the gap that Part B's solver closes.
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.integrate import solve_ivp

# SI, CODATA 2018 and IAU 2015 nominal solar values (Prša et al. 2016).
G = 6.67430e-11
K_B = 1.380649e-23
M_U = 1.66053906660e-27
M_SUN_KG = 1.3271244e20 / G
R_SUN_M = 6.957e8

XI_START = 1e-6     # integration starts on the series theta = 1 - xi^2/6 + n xi^4/120
N5_XI_MAX = 50.0    # n = 5 has no surface; its profile stops here


@dataclass(frozen=True)
class Polytrope:
    """One Lane-Emden solution, dimensionless."""

    n: float
    xi: np.ndarray       # from 0 to the surface xi_1 (or N5_XI_MAX for n = 5)
    theta: np.ndarray
    dtheta: np.ndarray   # dtheta/dxi
    xi1: float           # first zero of theta; inf for n = 5
    mass_constant: float  # -xi^2 theta' at xi_1: M = 4 pi alpha^3 rho_c x this
    concentration: float  # rho_c / rho_mean = -xi_1 / (3 theta'(xi_1)); inf for n = 5


def lane_emden(n: float, points: int = 400) -> Polytrope:
    """Solve the Lane-Emden equation for index n (0 to 5) on `points` radii out to the surface."""
    if not 0 <= n <= 5:
        raise ValueError(f"polytropic index {n} is outside 0-5")

    def rhs(xi, y):
        return [y[1], -max(y[0], 0.0) ** n - 2.0 * y[1] / xi]

    def surface(xi, y):
        return y[0]
    surface.terminal, surface.direction = True, -1

    x0 = XI_START
    y0 = [1 - x0**2 / 6 + n * x0**4 / 120, -x0 / 3 + n * x0**3 / 30]
    sol = solve_ivp(rhs, [x0, N5_XI_MAX], y0, events=surface, dense_output=True,
                    method="DOP853", rtol=1e-12, atol=1e-14)
    if sol.t_events[0].size:
        xi1, dtheta1 = float(sol.t_events[0][0]), float(sol.y_events[0][0][1])
        mass_constant, concentration = -xi1**2 * dtheta1, -xi1 / (3 * dtheta1)
    elif n == 5:
        xi1, mass_constant, concentration = np.inf, float(np.sqrt(3)), np.inf  # exact limits
    else:
        raise RuntimeError(f"no surface found for n = {n} before xi = {N5_XI_MAX}")

    xi = np.linspace(0.0, min(xi1, N5_XI_MAX), points)
    theta, dtheta = sol.sol(np.maximum(xi, x0))
    theta[0], dtheta[0] = 1.0, 0.0
    if np.isfinite(xi1):
        theta[-1] = 0.0
    return Polytrope(n, xi, theta, dtheta, xi1, mass_constant, concentration)


def exact_theta(n: int, xi: np.ndarray) -> np.ndarray:
    """The analytic solutions for n = 0, 1 and 5 (Chandrasekhar 1939, chapter IV)."""
    xi = np.asarray(xi, dtype=float)
    if n == 0:
        return 1 - xi**2 / 6
    if n == 1:
        return np.sinc(xi / np.pi)  # sin(xi) / xi, 1 at xi = 0
    if n == 5:
        return (1 + xi**2 / 3) ** -0.5
    raise ValueError(f"no exact solution for n = {n}")


def mean_molecular_weight(x: float, y: float, z: float) -> float:
    """Fully ionised gas: 1/mu = 2X + 3Y/4 + Z/2 (Kippenhahn, Weigert & Weiss 2012, eq. 4.30)."""
    return 1 / (2 * x + 0.75 * y + 0.5 * z)


@dataclass(frozen=True)
class PolytropeStar:
    """A polytrope scaled to a star's mass and radius, in SI; T from the ideal gas (beta = 1)."""

    rho_c_kg_m3: float
    p_c_pa: float
    t_c_k: float


def polytrope_star(poly: Polytrope, mass_msun: float, radius_rsun: float, mu: float) -> PolytropeStar:
    """Central density, pressure and temperature of a star of this mass and radius.

    rho_c = concentration x mean density; P_c = G M^2 / (4 pi (n + 1) (theta'(xi_1))^2 R^4)
    (Chandrasekhar 1939, chapter IV, eq. 80); T_c = mu m_u P_c / (k rho_c), ignoring radiation
    pressure, which is under 0.1% of P_c in the Sun's centre.
    """
    if not np.isfinite(poly.xi1):
        raise ValueError("an n = 5 polytrope has infinite radius")
    m, r = mass_msun * M_SUN_KG, radius_rsun * R_SUN_M
    rho_c = poly.concentration * m / (4 / 3 * np.pi * r**3)
    dtheta1 = -poly.mass_constant / poly.xi1**2
    p_c = G * m**2 / (4 * np.pi * (poly.n + 1) * dtheta1**2 * r**4)
    return PolytropeStar(rho_c, p_c, mu * M_U * p_c / (K_B * rho_c))


# ---- Part B: the zero-age main-sequence solver ------------------------------------------------
#
# Four structure equations in the mass coordinate m (Kippenhahn, Weigert & Weiss 2012, ch. 10):
#   dr/dm = 1 / (4 pi r^2 rho),  dP/dm = -G m / (4 pi r^4),  dL/dm = eps,
#   dT/dm = -G m T / (4 pi r^4 P) nabla.
# Fitting method (KWW 2012, section 12.1): integrate out from the centre and in from the surface,
# match at half the mass, and solve for central pressure, central temperature, radius and
# luminosity with scipy.optimize.root.
#
# Milestone 3: uniform composition, ideal gas plus radiation pressure, a constant opacity (electron
# scattering), radiative transport everywhere, and a power-law pp rate.
# Milestone 4: Kramers bound-free and free-free opacity plus electron scattering, and the analytic
# pp-chain and CNO-cycle rates. Milestone 5 adds convection.

SIGMA_SB = 5.670374419e-8
C_LIGHT = 299792458.0
A_RAD = 4 * SIGMA_SB / C_LIGHT
SIGMA_THOMSON = 6.6524587321e-29
L_SUN_W = 3.828e26   # IAU 2015 nominal (Prša et al. 2016)

# MIST v1.2 (Choi et al. 2016, eqs. 1-3): Z = Z_protosolar 10^[Fe/H] with Z_protosolar = 0.0142
# (Asplund et al. 2009), Y = Y_p + 1.5 Z, X = 1 - Y - Z. The released archive headers differ
# slightly (Z_init = 0.014286 and Y_init = 0.2703 at [Fe/H] 0), so the MIST comparison
# (milestone 5) reads X, Y and Z from the archive instead.
MIST_Z_SUN = 0.0142
MIST_Y_P = 0.249
MIST_DY_DZ = 1.5

# shortcut: the pp chain as a power law, eps = EPS_PP0 X^2 rho (T / 1e6 K)^4 in W/kg, a textbook fit
# near 1.5e7 K that is not yet source-checked; milestone 4 replaces it with the analytic pp and CNO
# rates.
EPS_PP0 = 1.07e-12

# Milestone 4. The coefficients below are as given in Kippenhahn, Weigert & Weiss 2012 (cgs), quoted
# from memory: the book is not in documentation/references, so each is listed in Source checks.md as
# not yet checked.
# Kramers opacity, cm^2/g: free-free 3.68e22 (1 - Z)(1 + X) rho T^-3.5, bound-free
# 4.34e25 Z (1 + X) rho T^-3.5, with the Gaunt and guillotine factors set to 1.
KAPPA_FF0_CGS = 3.68e22
KAPPA_BF0_CGS = 4.34e25
# pp chain, erg/g/s: 2.57e4 psi f11 g11 rho X^2 T9^(-2/3) exp(-3.381 T9^(-1/3)),
# g11 = 1 + 3.82 T9 + 1.51 T9^2 + 0.144 T9^3 - 0.0114 T9^4; psi (the pp II/III correction) and
# f11 (screening) are set to 1.
# CNO cycle, erg/g/s: 8.24e25 g14 X_CNO X rho T9^(-2/3) exp(-15.231 T9^(-1/3) - (T9 / 0.8)^2),
# g14 = 1 - 2.00 T9 + 3.41 T9^2 - 2.43 T9^3.
EPS_PP0_CGS = 2.57e4
EPS_CNO0_CGS = 8.24e25
# shortcut: C + N + O as a fixed share of Z, from Asplund et al. 2009's photospheric mass fractions
# (not yet source-checked); upgrade by reading the mixture MIST uses.
CNO_SHARE_OF_Z = 0.66


@dataclass(frozen=True)
class Composition:
    x: float
    y: float
    z: float

    @property
    def mu(self) -> float:
        return mean_molecular_weight(self.x, self.y, self.z)


def mist_composition(feh: float) -> Composition:
    """X, Y and Z at this [Fe/H] by Choi et al. 2016's eqs. 1-3."""
    z = MIST_Z_SUN * 10**feh
    y = MIST_Y_P + MIST_DY_DZ * z
    return Composition(1 - y - z, y, z)


def density(p, t, comp: Composition):
    """Ideal gas plus radiation: P = rho k T / (mu m_u) + a T^4 / 3 (KWW 2012, ch. 13)."""
    return (p - A_RAD * t**4 / 3) * comp.mu * M_U / (K_B * t)


def opacity_electron_scattering(comp: Composition) -> float:
    """Thomson scattering on free electrons, kappa = sigma_T (1 + X) / (2 m_u) (KWW 2012, eq. 17.2)."""
    return SIGMA_THOMSON * (1 + comp.x) / (2 * M_U)


def eps_pp_power_law(rho, t, comp: Composition):
    return EPS_PP0 * comp.x**2 * rho * (t / 1e6) ** 4


def opacity_kramers(rho, t, comp: Composition):
    """Kramers free-free plus bound-free opacity, m^2/kg (rho in kg/m^3)."""
    kappa_cgs = (KAPPA_FF0_CGS * (1 - comp.z) + KAPPA_BF0_CGS * comp.z) * (1 + comp.x) \
        * (rho * 1e-3) * t**-3.5
    return 0.1 * kappa_cgs


def opacity_m4(rho, t, comp: Composition):
    """Milestone 4: Kramers plus electron scattering."""
    return opacity_kramers(rho, t, comp) + opacity_electron_scattering(comp)


def eps_pp(rho, t, comp: Composition):
    """pp-chain energy generation, W/kg."""
    t9 = t * 1e-9
    g11 = 1 + 3.82 * t9 + 1.51 * t9**2 + 0.144 * t9**3 - 0.0114 * t9**4
    return 1e-4 * EPS_PP0_CGS * g11 * (rho * 1e-3) * comp.x**2 * t9 ** (-2 / 3) \
        * np.exp(-3.381 * t9 ** (-1 / 3))


def eps_cno(rho, t, comp: Composition):
    """CNO-cycle energy generation, W/kg."""
    t9 = t * 1e-9
    g14 = 1 - 2.00 * t9 + 3.41 * t9**2 - 2.43 * t9**3
    return 1e-4 * EPS_CNO0_CGS * g14 * CNO_SHARE_OF_Z * comp.z * comp.x * (rho * 1e-3) \
        * t9 ** (-2 / 3) * np.exp(-15.231 * t9 ** (-1 / 3) - (t9 / 0.8) ** 2)


def eps_m4(rho, t, comp: Composition):
    return eps_pp(rho, t, comp) + eps_cno(rho, t, comp)


def nabla_ad(p, t):
    """Adiabatic gradient of an ideal gas plus radiation, with beta = P_gas / P (KWW 2012,
    eq. 13.21): (1 + g) / (5/2 + 4 g), g = (1 - beta)(4 + beta) / beta^2; 0.4 when beta = 1."""
    beta = 1 - A_RAD * t**4 / (3 * p)
    g = (1 - beta) * (4 + beta) / beta**2
    return (1 + g) / (2.5 + 4 * g)


@lru_cache(maxsize=8)
def _opal(x: float, z: float):
    from .opacity import Opacity
    return Opacity(x, z)


def opacity_opal(rho, t, comp: Composition):
    """OPAL and Ferguson et al. 2005 tables, as MIST v1.2 used them (stellarforge.opacity)."""
    return _opal(comp.x, comp.z)(rho, t)


# Each milestone's (opacity, energy generation, convection, equation of state): the first two are
# functions of (rho, T, composition); with convection, the Schwarzschild criterion picks the smaller
# of the radiative and adiabatic gradients (KWW 2012, ch. 6), so convection is taken as fully
# efficient. Milestone 5 takes the plan's opacity upgrade (the tabulated opacities replace Kramers,
# which misses MIST by 0.8 dex in log L at 1 M☉) and adds H and He ionisation to the equation of
# state ("saha", stellarforge.eos), without which the model has no convective envelope.
PHYSICS = {
    3: (lambda rho, t, comp: opacity_electron_scattering(comp), eps_pp_power_law, False, "ideal"),
    4: (opacity_m4, eps_m4, False, "ideal"),
    5: (opacity_opal, eps_m4, "mlt", "saha"),
}

# MIST v1.2's mixing length in pressure scale heights (Choi et al. 2016, table 1).
ALPHA_MLT = 1.82


def nabla_mlt(rad, ad, t, rho, p, kappa, cp, delta, g, alpha=ALPHA_MLT):
    """The temperature gradient in a convective layer by mixing-length theory (Böhm-Vitense 1958, as
    in KWW 2012, section 7.2): with l = alpha H_P, H_P = P / (rho g),
    U = 3 a c T^3 / (c_P rho^2 kappa l^2) sqrt(8 H_P / (g delta)) and W = nabla_rad - nabla_ad,
    xi solves (xi - U)^3 + (8 U / 9)(xi^2 - U^2 - W) = 0 and nabla = xi^2 - U^2 + nabla_ad.
    MIST uses Henyey et al. 1965's variant, which differs only where the layer is optically thin.
    The KWW formulae are written from memory and listed in Source checks as not yet checked."""
    from scipy.optimize import brentq

    hp = p / (rho * g)
    ell = alpha * hp
    u = 3 * A_RAD * C_LIGHT * t**3 / (cp * rho**2 * kappa * ell**2) * np.sqrt(8 * hp / (g * delta))
    w = rad - ad

    # In z = xi - U (no cancellation when U is large): z^3 + (8 U / 9)(z^2 + 2 U z - W) = 0, with
    # a root between 0 (nabla = nabla_ad) and z_max = W / (sqrt(W + U^2) + U) (nabla = nabla_rad).
    z_max = w / (np.sqrt(w + u**2) + u)

    def cubic(z):
        return z**3 + 8 * u / 9 * (z**2 + 2 * u * z - w)
    if cubic(z_max) <= 0:      # rounding: convection carries a negligible share of the flux
        return rad
    z = brentq(cubic, 0.0, z_max, xtol=1e-300, rtol=1e-13)
    return z**2 + 2 * u * z + ad


@dataclass(frozen=True)
class MistZams:
    """MIST v1.2's zero-age main-sequence star (EEP 202) and the composition of its archive."""

    composition: Composition
    log_l_lsun: float
    log_r_rsun: float
    log_t_c_k: float
    log_rho_c_kg_m3: float

    def guess(self) -> tuple[float, float, float, float]:
        """(P_c Pa, T_c K, R R_sun, L L_sun) for solve_zams, P_c from the equation of state."""
        rho_c, t_c = 10**self.log_rho_c_kg_m3, 10**self.log_t_c_k
        p_c = rho_c * K_B * t_c / (self.composition.mu * M_U) + A_RAD * t_c**4 / 3
        return p_c, t_c, 10**self.log_r_rsun, 10**self.log_l_lsun


def mist_zams(mass_msun: float, feh: float) -> MistZams:
    """MIST's zero-age star at a grid [Fe/H], with X, Y and Z from that archive's header."""
    from . import evolution
    from .mist import GRIDS

    files = [f for f in GRIDS.glob("MIST_v1.2_*.npz") if abs(float(np.load(f)["feh"]) - feh) < 1e-9]
    if not files:
        raise ValueError(f"[Fe/H] {feh} is not a converted MIST grid metallicity")
    with np.load(files[0]) as grid:
        z, y = float(grid["zinit"]), float(grid["yinit"])
    v = evolution.build_track(mass_msun, feh).values
    k = 202 - 1   # EEP 202, the zero-age main sequence
    return MistZams(Composition(1 - y - z, y, z), float(v["log_l_lsun"][k]),
                    float(v["log_r_rsun"][k]), float(v["log_center_t_k"][k]),
                    float(v["log_center_rho_cgs"][k]) + 3)


@dataclass(frozen=True)
class ZamsModel:
    """A converged zero-age model; profiles run from the centre to the surface."""

    mass_msun: float
    composition: Composition
    p_c_pa: float
    t_c_k: float
    rho_c_kg_m3: float
    radius_rsun: float
    luminosity_lsun: float
    teff_k: float
    residual: float          # largest relative mismatch at the fitting point
    m_kg: np.ndarray
    r_m: np.ndarray
    p_pa: np.ndarray
    l_w: np.ndarray
    t_k: np.ndarray


class _Star:
    """The structure equations for one mass and composition, with one milestone's physics."""

    def __init__(self, mass_msun: float, comp: Composition, milestone: int):
        self.M = mass_msun * M_SUN_KG
        self.comp = comp
        opacity, eps, self.convection, eos = PHYSICS[milestone]
        self.kappa = lambda rho, t: opacity(rho, t, comp)
        self.eps = lambda rho, t: eps(rho, t, comp)
        if eos == "saha":
            from .eos import SahaEos
            saha = SahaEos(comp.x, comp.y, comp.z)
            self.density, self.nabla_ad, self.state = saha.density, saha.nabla_ad, saha.state
        else:
            self.density = lambda p, t: density(p, t, comp)
            self.nabla_ad = nabla_ad
            self.state = lambda p, t: (density(p, t, comp), nabla_ad(p, t), None, None)

    def nabla_rad(self, rho, t, p, lum_over_m):
        return 3 * self.kappa(rho, t) * lum_over_m * p / (16 * np.pi * A_RAD * C_LIGHT * G * t**4)

    def nabla(self, rho, t, p, lum_over_m, ad, cp, delta, g):
        """Radiative where the Schwarzschild criterion says so; in a convective layer adiabatic
        (milestone 4's `True`) or by mixing-length theory (milestone 5's "mlt")."""
        rad = self.nabla_rad(rho, t, p, lum_over_m)
        if not self.convection or rad <= ad:
            return rad
        if self.convection == "mlt":
            return nabla_mlt(rad, ad, t, rho, p, self.kappa(rho, t), cp, delta, g)
        return ad

    def is_convective(self, p, t, lum, m):
        """True where the Schwarzschild criterion gives convection."""
        rho, ad, _, _ = self.state(p, t)
        return bool(self.nabla_rad(rho, t, p, lum / m) > ad)

    def derivs(self, m, r, p, lum, t):
        rho, ad, cp, delta = self.state(p, t)
        if not np.all(rho > 0):
            raise FloatingPointError("negative density")
        nabla = self.nabla(rho, t, p, lum / m, ad, cp, delta, G * m / r**2)
        dr = 1 / (4 * np.pi * r**2 * rho)
        dp = -G * m / (4 * np.pi * r**4)
        return dr, dp, self.eps(rho, t), dp * t / p * nabla

    # State y = (ln r, ln P, L / L_sun, ln T): the logarithms keep steps sensible over many decades.
    def _rhs_log(self, m, y):
        r, p, lum, t = np.exp(y[0]), np.exp(y[1]), y[2] * L_SUN_W, np.exp(y[3])
        dr, dp, dl, dt = self.derivs(m, r, p, lum, t)
        return np.array([dr / r, dp / p, dl / L_SUN_W, dt / t])

    def centre(self, p_c, t_c, m):
        """Series expansion at small m (KWW 2012, eqs. 11.3-11.9). A convective core follows the
        adiabat, T = T_c (P / P_c)^nabla_ad."""
        rho_c = self.density(p_c, t_c)
        if not rho_c > 0:
            raise FloatingPointError("negative central density")
        eps_c = self.eps(rho_c, t_c)
        r = (3 * m / (4 * np.pi * rho_c)) ** (1 / 3)
        p = p_c - 3 * G / (8 * np.pi) * (4 * np.pi * rho_c / 3) ** (4 / 3) * m ** (2 / 3)
        t4 = t_c**4 - (1 / (2 * A_RAD * C_LIGHT)) * (3 / (4 * np.pi)) ** (2 / 3) \
            * self.kappa(rho_c, t_c) \
            * eps_c * rho_c ** (4 / 3) * m ** (2 / 3)
        ad = self.nabla_ad(p_c, t_c)
        if self.convection and self.nabla_rad(rho_c, t_c, p_c, eps_c) > ad and p > 0:
            t4 = (t_c * (p / p_c) ** ad) ** 4
        if not (p > 0 and t4 > 0):
            raise FloatingPointError("central expansion breaks down at the first step")
        return np.array([np.log(r), np.log(p), eps_c * m / L_SUN_W, 0.25 * np.log(t4)])

    def surface(self, radius, lum):
        """Photosphere: T = Teff with L = 4 pi R^2 sigma Teff^4, P = (2/3) G M / (R^2 kappa)
        (KWW 2012, section 11.2)."""
        from scipy.optimize import brentq

        t = (lum / (4 * np.pi * radius**2 * SIGMA_SB)) ** 0.25
        g = G * self.M / radius**2

        # kappa depends on the density, and so on P: solve P = (2/3) g / kappa(rho(P, T), T) in ln P
        def gap(ln_p):
            return ln_p - np.log(2 / 3 * g / self.kappa(self.density(np.exp(ln_p), t), t))
        # gap rises with P: step from 1e4 Pa (a typical photosphere) towards the sign change. A
        # tabulated opacity raises ValueError outside its density range, and radiation pressure
        # sets a floor; reaching either rejects the trial.
        floor = np.log(A_RAD * t**4 / 3 * (1 + 1e-9))
        a = max(np.log(1e4), floor + 1.0)
        try:
            step = -1.0 if gap(a) > 0 else 1.0
            while True:
                b = max(a + step, floor)
                if np.sign(gap(b)) != np.sign(gap(a)):
                    break
                if b == floor:
                    raise FloatingPointError("radiation pressure alone exceeds the photosphere's")
                a = b
        except ValueError as e:
            raise FloatingPointError(f"no photosphere inside the opacity table: {e}") from e
        p = np.exp(brentq(gap, min(a, b), max(a, b), xtol=1e-12))
        return np.array([np.log(radius), np.log(p), lum / L_SUN_W, np.log(t)])

    def outward(self, p_c, t_c, m_fit, dense=False):
        m0 = 1e-10 * self.M
        return solve_ivp(self._rhs_log, [m0, m_fit], self.centre(p_c, t_c, m0), method="Radau",
                         rtol=1e-8, atol=1e-10, dense_output=dense)

    def inward(self, radius, lum, m_fit, dense=False):
        # Independent variable s = ln(1 - m/M): resolves the thin outer layers. The photosphere is
        # placed at 1 - m/M = 1e-12, which neglects the mass above it.
        def rhs(s, y):
            return self._rhs_log(self.M * (1 - np.exp(s)), y) * (-self.M * np.exp(s))
        return solve_ivp(rhs, [np.log(1e-12), np.log(1 - m_fit / self.M)],
                         self.surface(radius, lum), method="Radau", rtol=1e-8, atol=1e-10,
                         dense_output=dense)

    def mismatch(self, x, m_fit):
        p_c, t_c, radius, lum = np.exp(x)
        try:
            out, inn = self.outward(p_c, t_c, m_fit), self.inward(radius, lum, m_fit)
        except (FloatingPointError, ValueError):   # a trial the physics rejects
            return np.full(4, 1e3)
        if out.status != 0 or inn.status != 0:
            return np.full(4, 1e3)
        a, b = out.y[:, -1], inn.y[:, -1]
        return np.array([a[0] - b[0], a[1] - b[1], (a[2] - b[2]) / b[2], a[3] - b[3]])


def solve_zams(mass_msun: float = 1.0, feh: float = 0.0, guess: tuple | None = None,
               points: int = 200, milestone: int = 5,
               composition: Composition | None = None) -> ZamsModel:
    """A zero-age main-sequence model by fitting at half the mass, with one milestone's physics.
    `guess` is (P_c Pa, T_c K, R R_sun, L L_sun); the default scales the n = 3 polytrope to the
    star. `composition` defaults to Choi et al. 2016's eqs. 1-3 at this [Fe/H]. Raises
    RuntimeError if the fit does not converge."""
    from scipy.optimize import root

    comp = composition or mist_composition(feh)
    star = _Star(mass_msun, comp, milestone)
    if guess is None and milestone == 5:
        try:   # the plan's milestone 5 starts from MIST's zero-age star of the same mass and [Fe/H]
            guess = mist_zams(mass_msun, feh).guess()
        except (FileNotFoundError, ValueError):
            guess = None
    if guess is None:
        sun = polytrope_star(lane_emden(3), mass_msun, mass_msun**0.8, comp.mu)
        guess = (sun.p_c_pa, sun.t_c_k, mass_msun**0.8, mass_msun**3.5)
    x0 = np.log([guess[0], guess[1], guess[2] * R_SUN_M, guess[3] * L_SUN_W])
    m_fit = 0.5 * star.M
    sol = root(star.mismatch, x0, args=(m_fit,), method="hybr", options={"xtol": 1e-10})
    residual = float(np.max(np.abs(star.mismatch(sol.x, m_fit))))
    if residual > 1e-6:
        raise RuntimeError(f"zero-age fit did not converge at {mass_msun} M☉ (mismatch {residual:.2g})")

    p_c, t_c, radius, lum = np.exp(sol.x)
    out, inn = star.outward(p_c, t_c, m_fit, dense=True), star.inward(radius, lum, m_fit, dense=True)
    m_in = np.linspace(1e-10 * star.M, m_fit, points // 2)
    # Outer half evenly in log(1 - m/M), so the thin envelope and atmosphere are resolved; the
    # fitting point appears once.
    q_out = np.geomspace(1 - m_fit / star.M, 1e-12, points - points // 2 + 1)[1:]
    y = np.hstack([out.sol(m_in), inn.sol(np.log(q_out))])
    m = np.hstack([m_in, star.M * (1 - q_out)])
    return ZamsModel(
        mass_msun=mass_msun, composition=comp, p_c_pa=p_c, t_c_k=t_c,
        rho_c_kg_m3=float(star.density(p_c, t_c)), radius_rsun=radius / R_SUN_M,
        luminosity_lsun=lum / L_SUN_W,
        teff_k=float((lum / (4 * np.pi * radius**2 * SIGMA_SB)) ** 0.25), residual=residual,
        m_kg=m, r_m=np.exp(y[0]), p_pa=np.exp(y[1]), l_w=y[2] * L_SUN_W, t_k=np.exp(y[3]))
