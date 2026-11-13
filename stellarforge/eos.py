"""Equation of state with hydrogen and helium ionisation (Kippenhahn, Weigert & Weiss 2012, ch. 14).

A non-degenerate ideal gas of H, He and metals plus radiation. The ionisation of H (13.598 eV) and
of He (24.587 and 54.418 eV, NIST) follows the Saha equation,

    n_{i+1} n_e / n_i = 2 (g_{i+1} / g_i) (2 pi m_e k T / h^2)^{3/2} exp(-chi_i / k T),

solved for the electron density on a grid of log T and log rho. The specific entropy of the
mixture (Sackur-Tetrode for each species, plus radiation) gives, by finite differences, the
adiabatic gradient nabla_ad = 1 / (dlnP/dlnT - dlnP/dlnrho * (ds/dlnT) / (ds/dlnrho)), the specific
heat c_P = T (ds/dT)_P and delta = -(dln rho / dln T)_P, which mixing-length convection needs.

shortcut: the Saha equation ignores pressure ionisation, so in deep, dense layers it wrongly
recombines the gas (about 40% neutral hydrogen at the Sun's centre). Ionisation is therefore blended
smoothly to complete between log T 6.0 and 6.5, where Saha already gives a nearly ionised envelope;
replace with OPAL or a pressure-ionisation model if the deep interior needs better.
shortcut: metals count as neutral atoms of mass 16 m_u that give one electron per hydrogen
ionisation fraction times Z/2 per m_u; their ionisation is not computed.
"""

from functools import lru_cache

import numpy as np
from scipy.interpolate import RectBivariateSpline

K_B = 1.380649e-23
M_U = 1.66053906660e-27
M_E = 9.1093837015e-31
H_PLANCK = 6.62607015e-34
EV = 1.602176634e-19
A_RAD = 4 * 5.670374419e-8 / 299792458.0
M_H = 1.00784 * M_U
M_HE = 4.002602 * M_U
A_METAL = 16.0

# NIST Handbook of Basic Atomic Spectroscopic Data (hydrogen and helium tables)
CHI_H, CHI_HE1, CHI_HE2 = 13.598433 * EV, 24.587387 * EV, 54.417760 * EV
# Ground-state statistical weights: H I 2, H II 1; He I 1, He II 2, He III 1; electrons 2.
G = {"h0": 2, "h1": 1, "he0": 1, "he1": 2, "he2": 1, "e": 2}

LOG_T = np.arange(3.3, 7.8001, 0.01)
LOG_RHO = np.arange(-11.0, 6.0001, 0.02)     # kg/m^3
FULL_IONISATION_LOG_T = (6.0, 6.5)


def _thermal_volume(mass, t):
    """lambda^3 = (h^2 / (2 pi m k T))^{3/2}."""
    return (H_PLANCK**2 / (2 * np.pi * mass * K_B * t)) ** 1.5


def ionisation(rho, t, x, y, z):
    """Number densities (m^-3) of each species, by Saha, before the full-ionisation blend."""
    n_h, n_he = x * rho / M_H, y * rho / M_HE
    saha = 2 / _thermal_volume(M_E, t)        # 2 (2 pi m_e k T / h^2)^{3/2}
    s_h = saha * G["h1"] / G["h0"] * np.exp(-CHI_H / (K_B * t))
    s_he1 = saha * G["he1"] / G["he0"] * np.exp(-CHI_HE1 / (K_B * t))
    s_he2 = saha * G["he2"] / G["he1"] * np.exp(-CHI_HE2 / (K_B * t))
    metal_e = z * rho / (2 * M_U)

    def fractions(ne):
        xh = s_h / (ne + s_h)
        d = ne**2 + s_he1 * ne + s_he1 * s_he2
        return xh, s_he1 * ne / d, s_he1 * s_he2 / d

    def electrons(ne):
        xh, f1, f2 = fractions(ne)
        return n_h * xh + n_he * (f1 + 2 * f2) + metal_e * xh

    # n_e is the root of electrons(n_e) - n_e, which falls with n_e; bisect in log n_e.
    lo = np.full(np.broadcast(rho, t).shape, -40.0)
    hi = np.log(n_h + 2 * n_he + metal_e) + 1e-12 + np.zeros_like(lo)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        up = electrons(np.exp(mid)) > np.exp(mid)
        lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
    ne = np.exp(0.5 * (lo + hi))
    xh, f1, f2 = fractions(ne)
    return xh, f1, f2


@lru_cache(maxsize=8)
class SahaEos:
    """P, specific entropy and nabla_ad for one composition, tabulated on (log T, log rho)."""

    def __init__(self, x: float, y: float, z: float):
        self.x, self.y, self.z = x, y, z
        lt, lr = np.meshgrid(LOG_T, LOG_RHO, indexing="ij")
        t, rho = 10.0**lt, 10.0**lr
        xh, f1, f2 = ionisation(rho, t, x, y, z)
        lo, hi = FULL_IONISATION_LOG_T
        w = np.clip((lt - lo) / (hi - lo), 0, 1)
        w = 0.5 - 0.5 * np.cos(np.pi * w)           # 0 below lo, 1 above hi
        xh = xh + w * (1 - xh)
        f2 = f2 + w * (1 - f2)
        f1 = (1 - w) * f1
        f0 = np.clip(1 - f1 - f2, 0, 1)

        n_h, n_he, n_z = x * rho / M_H, y * rho / M_HE, z * rho / (A_METAL * M_U)
        species = {   # (number density, mass, statistical weight)
            "h0": (n_h * (1 - xh), M_H, G["h0"]), "h1": (n_h * xh, M_H, G["h1"]),
            "he0": (n_he * f0, M_HE, G["he0"]), "he1": (n_he * f1, M_HE, G["he1"]),
            "he2": (n_he * f2, M_HE, G["he2"]), "z": (n_z, A_METAL * M_U, 1),
        }
        ne = n_h * xh + n_he * (f1 + 2 * f2) + z * rho / (2 * M_U) * xh
        species["e"] = (ne, M_E, G["e"])
        n_total = sum(n for n, _, _ in species.values())
        p = n_total * K_B * t + A_RAD * t**4 / 3
        # Sackur-Tetrode: S = sum N k (5/2 - ln(n lambda^3 / g)); the ionisation energies cancel
        # between U and F (KWW 2012, ch. 14), plus radiation 4 a T^3 / (3 rho), per unit mass.
        with np.errstate(invalid="ignore", over="ignore", divide="ignore"):   # empty species: masked by where
            s = sum(np.where(n > 0, n * K_B * (2.5 - np.log(np.maximum(n, 1e-300)
                                                         * _thermal_volume(m, t) / g)), 0.0)
                for n, m, g in species.values()) / rho + 4 * A_RAD * t**3 / (3 * rho)

        ln_p = np.log(p)
        dp_dt, dp_dr = np.gradient(ln_p, LOG_T * np.log(10), LOG_RHO * np.log(10))
        ds_dt, ds_dr = np.gradient(s, LOG_T * np.log(10), LOG_RHO * np.log(10))
        nabla_ad = 1 / (dp_dt - dp_dr * ds_dt / ds_dr)
        # -(dln rho / dln T) at constant P. Where radiation pressure is all there is (hot, tenuous
        # corner of the table, never inside a star), P barely depends on rho: cap delta there so
        # the splines stay finite.
        delta = np.minimum(dp_dt / np.maximum(dp_dr, 1e-6), 1e3)
        cp = ds_dt - ds_dr * delta          # T (ds/dT) at constant P, J/(kg K)
        self.mu = rho * K_B * t / ((n_total) * K_B * t * M_U)      # mean molecular weight
        self._ln_p = RectBivariateSpline(LOG_T, LOG_RHO, ln_p)
        # Its own spline for dlnP/dlog10(rho): the spline derivative (dy=1) costs ~1 ms per call
        self._ln_p_slope = RectBivariateSpline(LOG_T, LOG_RHO, dp_dr * np.log(10))
        self._nabla_ad = RectBivariateSpline(LOG_T, LOG_RHO, nabla_ad)
        self._mu = RectBivariateSpline(LOG_T, LOG_RHO, self.mu)
        self._delta = RectBivariateSpline(LOG_T, LOG_RHO, delta)
        self._cp = RectBivariateSpline(LOG_T, LOG_RHO, cp)

    def _log_rho(self, p, t):
        """log10 rho from P and T by Newton's method on the tabulated ln P (rho increases P)."""
        lt = np.log10(t)
        if not (LOG_T[0] <= lt <= LOG_T[-1]):
            raise ValueError(f"log T {lt:.3f} outside the equation-of-state table")
        p_gas = p - A_RAD * t**4 / 3
        if not p_gas > 0:
            raise ValueError("radiation pressure exceeds the total pressure")
        lr = np.log10(p_gas * 0.6 * M_U / (K_B * t))      # ionised ideal gas as the first guess
        target = np.log(p)
        for _ in range(50):
            lr = min(max(lr, LOG_RHO[0]), LOG_RHO[-1])
            f = self._ln_p(lt, lr)[0, 0] - target
            slope = self._ln_p_slope(lt, lr)[0, 0]
            step = f / slope
            lr -= step
            if abs(step) < 1e-11:
                break
        if not (LOG_RHO[0] <= lr <= LOG_RHO[-1]) or abs(step) > 1e-6:
            raise ValueError(f"no density in the table for P {p:.3g} Pa, T {t:.3g} K")
        return lr

    def state(self, p, t):
        """(rho, nabla_ad, c_P, delta) at this P and T."""
        lt, lr = np.log10(t), self._log_rho(p, t)
        return (10.0**lr, float(self._nabla_ad(lt, lr)[0, 0]), float(self._cp(lt, lr)[0, 0]),
                float(self._delta(lt, lr)[0, 0]))

    def density(self, p, t):
        return 10.0 ** self._log_rho(p, t)

    def nabla_ad(self, p, t):
        return float(self._nabla_ad(np.log10(t), self._log_rho(p, t))[0, 0])

    def mean_molecular_weight(self, p, t):
        return float(self._mu(np.log10(t), self._log_rho(p, t))[0, 0])
