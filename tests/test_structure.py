"""structure.py, Part A: Lane-Emden polytropes against exact solutions and published constants
(numbers from the build plan's Validation table)."""

import numpy as np
import pytest

from stellarforge.structure import exact_theta, lane_emden, mean_molecular_weight, polytrope_star


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
