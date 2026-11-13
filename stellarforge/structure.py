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
