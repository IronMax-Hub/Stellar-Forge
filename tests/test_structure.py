"""structure.py: Lane-Emden polytropes against exact solutions and published constants (Part A),
then the zero-age main-sequence solver's milestones (Part B); numbers from the build plan's
Validation table."""

import numpy as np
import pytest
from scipy.optimize import brentq

from stellarforge import evolution, opacity
from stellarforge.structure import (
    A_RAD,
    L_SUN_W,
    M_SUN_KG,
    R_SUN_M,
    SIGMA_SB,
    _Star,
    eps_cno,
    eps_pp,
    exact_theta,
    lane_emden,
    mean_molecular_weight,
    mist_composition,
    mist_zams,
    nabla_ad,
    nabla_mlt,
    polytrope_star,
    solve_zams,
)


@pytest.mark.parametrize("n", [0, 1, 5])
def test_exact_solutions(n):
    poly = lane_emden(n)
    np.testing.assert_allclose(poly.theta, exact_theta(n, poly.xi), atol=1e-9)
    np.testing.assert_allclose(poly.dtheta[1:], np.gradient(exact_theta(n, poly.xi), poly.xi)[1:],
                               atol=2e-3)  # finite-difference slope, a sanity check only


def test_exact_surfaces():
    assert lane_emden(0).xi1 == pytest.approx(np.sqrt(6), rel=1e-9)
    assert lane_emden(0).concentration == pytest.approx(1.0, rel=1e-9)
    assert lane_emden(1).xi1 == pytest.approx(np.pi, rel=1e-9)
    assert lane_emden(1).concentration == pytest.approx(np.pi**2 / 3, rel=1e-9)
    assert lane_emden(5).xi1 == np.inf


@pytest.mark.parametrize("n, xi1, mass_constant, concentration", [
    (1.5, 3.65375, 2.71406, 5.99071),   # Chandrasekhar 1939, table 4
    (3.0, 6.89685, 2.01824, 54.1825),
])
def test_published_constants(n, xi1, mass_constant, concentration):
    poly = lane_emden(n)
    assert poly.xi1 == pytest.approx(xi1, abs=1e-5)
    assert poly.mass_constant == pytest.approx(mass_constant, abs=1e-5)
    assert poly.concentration == pytest.approx(concentration, abs=2e-5)


def test_surface_and_monotonic_for_every_exported_index():
    for n in np.arange(0, 5.5, 0.5):
        poly = lane_emden(n)
        assert poly.theta[0] == 1 and np.all(np.diff(poly.theta) < 0)
        assert (poly.theta[-1] == 0) == (n < 5)


def test_eddington_standard_model_sun():
    mu = mean_molecular_weight(0.70, 0.28, 0.02)
    assert mu == pytest.approx(0.617, abs=5e-4)
    sun = polytrope_star(lane_emden(3), 1.0, 1.0, mu)
    assert round(sun.t_c_k, -5) == 1.21e7
    assert sun.rho_c_kg_m3 == pytest.approx(7.6e4, rel=0.01)  # 54.18 x the mean density


def test_rejects_index_outside_range():
    with pytest.raises(ValueError):
        lane_emden(5.5)


def test_mist_composition():
    sun = mist_composition(0.0)   # Choi et al. 2016, table 1: X = 0.7154, Y = 0.2703, Z = 0.0142
    assert (sun.y, sun.z) == pytest.approx((0.2703, 0.0142))
    assert sun.x + sun.y + sun.z == pytest.approx(1.0)
    assert mist_composition(-2.0).y == pytest.approx(0.249 + 1.5 * 0.000142)


@pytest.fixture(scope="module")
def sun_m3():
    return solve_zams(1.0, 0.0, milestone=3)


def test_milestone_3_sun_like_model_converges(sun_m3):
    """Milestone 3: uniform composition, ideal gas plus radiation, electron-scattering opacity.
    It must converge and be self-consistent; matching MIST waits for milestones 4 and 5."""
    z = sun_m3
    assert z.residual < 1e-6
    n = len(z.m_kg)
    assert len(z.r_m) == len(z.p_pa) == len(z.l_w) == len(z.t_k) == n == 200
    assert np.all(np.diff(z.m_kg) > 0) and np.all(np.diff(z.r_m) > 0)
    assert np.all(np.diff(z.p_pa) < 0) and np.all(np.diff(z.t_k) < 0)
    assert np.all(np.diff(z.l_w) >= 0)
    assert z.m_kg[-1] == pytest.approx(M_SUN_KG) and z.r_m[-1] == pytest.approx(z.radius_rsun * R_SUN_M)
    assert z.l_w[-1] == pytest.approx(z.luminosity_lsun * L_SUN_W)
    lum = 4 * np.pi * (z.radius_rsun * R_SUN_M) ** 2 * SIGMA_SB * z.teff_k**4
    assert lum == pytest.approx(z.luminosity_lsun * L_SUN_W)
    assert 1e7 < z.t_c_k < 3e7   # hydrogen burning temperatures


def test_milestone_3_is_more_concentrated_than_uniform(sun_m3):
    """Central density above the mean, as in every polytrope with n > 0."""
    z = sun_m3
    mean = M_SUN_KG / (4 / 3 * np.pi * (z.radius_rsun * R_SUN_M) ** 3)
    assert z.rho_c_kg_m3 > 10 * mean


def test_adiabatic_gradient_limits():
    assert nabla_ad(1e16, 1e7) == pytest.approx(0.4, abs=1e-3)          # ideal gas
    assert nabla_ad(A_RAD * 1e28 / 3 * (1 + 1e-9), 1e7) == pytest.approx(0.25)  # radiation


def test_cno_overtakes_pp_near_18_million_k():
    """The textbook crossover is about 1.7-1.8e7 K; the rates are not yet source-checked, so the
    window is wide."""
    sun = mist_composition(0.0)
    crossover = brentq(lambda t: np.log(eps_cno(1e5, t, sun) / eps_pp(1e5, t, sun)), 1e7, 4e7)
    assert 1.6e7 < crossover < 2.0e7


# Milestone 4's converged 1 M☉ star with convection, from which milestone 4 alone converges.
KRAMERS_SUN = (5.302e15, 1.0661e7, 1.1698, 0.11221)


def test_milestone_4_converges_from_close_by():
    """Kramers plus electron scattering, pp and CNO, radiative only. From the n = 3 polytrope the
    central radiative gradient is about 12 and the fit fails; from close by it converges."""
    m4 = solve_zams(1.0, 0.0, milestone=4, guess=KRAMERS_SUN)
    assert m4.residual < 1e-6
    assert np.all(np.diff(m4.t_k) < 0) and np.all(np.diff(m4.l_w) >= 0)
    assert np.log10(m4.luminosity_lsun) == pytest.approx(-0.95, abs=0.01)


needs_mist_and_opal = pytest.mark.skipif(
    not (list(evolution.GRIDS.glob("*.npz")) and opacity.TABLES.exists()),
    reason="MIST grid or opacity tables not converted; run `make data`")


@pytest.fixture(scope="module")
def gate():
    mist = mist_zams(1.0, 0.0)
    return mist, solve_zams(1.0, 0.0, composition=mist.composition)


@needs_mist_and_opal
def test_milestone_5_gate_luminosity_and_central_temperature(gate):
    """The gate at 1 M☉, [Fe/H] 0, X Y Z from MIST's archive: log L within 0.1 dex, log Tc within
    0.05 dex of MIST's zero-age EEP."""
    mist, model = gate
    assert model.residual < 1e-6
    assert np.log10(model.luminosity_lsun) == pytest.approx(mist.log_l_lsun, abs=0.1)
    assert np.log10(model.t_c_k) == pytest.approx(mist.log_t_c_k, abs=0.05)


@needs_mist_and_opal
def test_milestone_5_gate_radius_and_convective_envelope(gate):
    """log R within 0.1 dex needs the ionising equation of state and mixing-length convection:
    without them the model has no convective envelope and misses by +0.17 dex."""
    mist, model = gate
    assert np.log10(model.radius_rsun) == pytest.approx(mist.log_r_rsun, abs=0.1)
    star = _Star(1.0, mist.composition, 5)
    conv = np.array([star.is_convective(p, t, lum, m)
                     for p, t, lum, m in zip(model.p_pa, model.t_k, model.l_w, model.m_kg)])
    assert not conv[0]                      # a radiative core at 1 M☉
    first, last = np.flatnonzero(conv)[[0, -1]]
    assert np.all(conv[first:last + 1])     # one convective envelope ...
    assert 0.6 < model.r_m[first] / model.r_m[-1] < 0.9
    assert model.r_m[last] / model.r_m[-1] > 0.99   # ... up to just below the photosphere


def test_mixing_length_gradient_lies_between_the_limits():
    kwargs = {"t": 1e5, "rho": 1e-2, "p": 1e8, "cp": 3e4, "delta": 1.0, "g": 274.0}
    for kappa in (1e-2, 1.0, 1e3):           # from inefficient to efficient convection
        nabla = nabla_mlt(rad=2.0, ad=0.4, kappa=kappa, **kwargs)
        assert 0.4 < nabla < 2.0
    assert nabla_mlt(rad=2.0, ad=0.4, kappa=1e3, **{**kwargs, "rho": 1e3, "p": 1e13}) \
        == pytest.approx(0.4, abs=1e-3)      # dense and opaque: almost adiabatic
    assert nabla_mlt(rad=2.0, ad=0.4, kappa=1e-6, **{**kwargs, "rho": 1e-8, "p": 1e2}) \
        == pytest.approx(2.0, rel=1e-2)      # thin and transparent: almost radiative
