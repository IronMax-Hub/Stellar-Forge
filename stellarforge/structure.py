"""Stellar structure from first principles (build plan, Phase 4).

Part A: polytropes. The Lane-Emden equation (Chandrasekhar 1939, chapter IV)

    (1/xi^2) d/dxi (xi^2 dtheta/dxi) = -theta^n,   theta(0) = 1, theta'(0) = 0,

is solved with SciPy for any index 0 <= n <= 5. Density is rho = rho_c theta^n and pressure
P = K rho^(1 + 1/n). The cases n = 0, 1 and 5 have exact solutions, which the tests compare against.
Applied to the Sun, n = 3 is Eddington's standard model; its central temperature is 1.21e7 K against
1.571e7 K in full solar models, the gap that Part B's solver closes.
"""

from dataclasses import dataclass

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
# scattering), radiative transport everywhere, and a power-law pp rate. Milestones 4 and 5 replace
# the opacity, the energy rate and the transport.

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
    """The structure equations for one mass and composition, with milestone 3's physics."""

    def __init__(self, mass_msun: float, comp: Composition):
        self.M = mass_msun * M_SUN_KG
        self.comp = comp
        self.kappa = opacity_electron_scattering(comp)

    def derivs(self, m, r, p, lum, t):
        rho = density(p, t, self.comp)
        if not np.all(rho > 0):
            raise FloatingPointError("negative density")
        nabla = 3 * self.kappa * lum * p / (16 * np.pi * A_RAD * C_LIGHT * G * m * t**4)
        dr = 1 / (4 * np.pi * r**2 * rho)
        dp = -G * m / (4 * np.pi * r**4)
        return dr, dp, eps_pp_power_law(rho, t, self.comp), dp * t / p * nabla

    # State y = (ln r, ln P, L / L_sun, ln T): the logarithms keep steps sensible over many decades.
    def _rhs_log(self, m, y):
        r, p, lum, t = np.exp(y[0]), np.exp(y[1]), y[2] * L_SUN_W, np.exp(y[3])
        dr, dp, dl, dt = self.derivs(m, r, p, lum, t)
        return np.array([dr / r, dp / p, dl / L_SUN_W, dt / t])

    def centre(self, p_c, t_c, m):
        """Series expansion at small m (KWW 2012, eqs. 11.3-11.9), radiative core."""
        rho_c = density(p_c, t_c, self.comp)
        eps_c = eps_pp_power_law(rho_c, t_c, self.comp)
        r = (3 * m / (4 * np.pi * rho_c)) ** (1 / 3)
        p = p_c - 3 * G / (8 * np.pi) * (4 * np.pi * rho_c / 3) ** (4 / 3) * m ** (2 / 3)
        t4 = t_c**4 - (1 / (2 * A_RAD * C_LIGHT)) * (3 / (4 * np.pi)) ** (2 / 3) * self.kappa \
            * eps_c * rho_c ** (4 / 3) * m ** (2 / 3)
        return np.array([np.log(r), np.log(p), eps_c * m / L_SUN_W, 0.25 * np.log(t4)])

    def surface(self, radius, lum):
        """Photosphere: T = Teff with L = 4 pi R^2 sigma Teff^4, P = (2/3) G M / (R^2 kappa)
        (KWW 2012, section 11.2)."""
        t = (lum / (4 * np.pi * radius**2 * SIGMA_SB)) ** 0.25
        p = 2 / 3 * G * self.M / (radius**2 * self.kappa)
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
        except FloatingPointError:
            return np.full(4, 1e3)
        if out.status != 0 or inn.status != 0:
            return np.full(4, 1e3)
        a, b = out.y[:, -1], inn.y[:, -1]
        return np.array([a[0] - b[0], a[1] - b[1], (a[2] - b[2]) / b[2], a[3] - b[3]])


def solve_zams(mass_msun: float = 1.0, feh: float = 0.0, guess: tuple | None = None,
               points: int = 200) -> ZamsModel:
    """A zero-age main-sequence model by fitting at half the mass. `guess` is (P_c Pa, T_c K, R
    R_sun, L L_sun); the default scales the n = 3 polytrope to the star. Raises RuntimeError if the
    fit does not converge."""
    from scipy.optimize import root

    comp = mist_composition(feh)
    star = _Star(mass_msun, comp)
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
    q_out = np.linspace(1 - m_fit / star.M, 1e-12, points - points // 2 + 1)[1:]  # fit point once
    y = np.hstack([out.sol(m_in), inn.sol(np.log(q_out))])
    m = np.hstack([m_in, star.M * (1 - q_out)])
    return ZamsModel(
        mass_msun=mass_msun, composition=comp, p_c_pa=p_c, t_c_k=t_c,
        rho_c_kg_m3=float(density(p_c, t_c, comp)), radius_rsun=radius / R_SUN_M,
        luminosity_lsun=lum / L_SUN_W,
        teff_k=float((lum / (4 * np.pi * radius**2 * SIGMA_SB)) ** 0.25), residual=residual,
        m_kg=m, r_m=np.exp(y[0]), p_pa=np.exp(y[1]), l_w=y[2] * L_SUN_W, t_k=np.exp(y[3]))
