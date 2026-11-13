"""eos.py: the Saha equation of state in its limits, and through ionisation zones."""

import numpy as np
import pytest

from stellarforge.eos import SahaEos, ionisation
from stellarforge.structure import mean_molecular_weight

X, Y, Z = 0.7154, 0.2703, 0.0143


@pytest.fixture(scope="module")
def eos():
    return SahaEos(X, Y, Z)


def test_neutral_and_fully_ionised_limits(eos):
    neutral = 1 / (X / 1.00784 + Y / 4.002602 + Z / 16)        # atoms only
    assert eos.mean_molecular_weight(1e4, 4000) == pytest.approx(neutral, rel=0.01)
    assert eos.mean_molecular_weight(1e15, 1e7) == pytest.approx(
        mean_molecular_weight(X, Y, Z), rel=0.01)
    for p, t in ((1e4, 4000), (1e15, 1e7)):
        assert eos.nabla_ad(p, t) == pytest.approx(0.4, abs=0.01)   # monatomic ideal gas


def test_ionisation_zones_lower_the_adiabatic_gradient(eos):
    assert eos.nabla_ad(1e7, 2e4) < 0.2        # hydrogen half ionised
    _, _, cp, delta = eos.state(1e7, 2e4)
    assert delta > 1.5 and cp > 2 * 2.5 * 1.380649e-23 / (0.62 * 1.66054e-27)


def test_saha_hydrogen_fraction_rises_with_temperature():
    xh = [ionisation(1e-3, t, X, Y, Z)[0] for t in (5e3, 1e4, 2e4, 5e4)]
    assert np.all(np.diff(xh) > 0) and xh[0] < 1e-3 and xh[-1] > 0.99


def test_density_inverts_pressure(eos):
    rho = eos.density(1e9, 5e4)
    assert eos.density(1e9, 5e4) == pytest.approx(rho)
    with pytest.raises(ValueError):
        eos.density(1e9, 1e9)                  # outside the table
