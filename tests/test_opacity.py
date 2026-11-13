"""opacity.py: the MESA table reader, and the OPAL tables at a grid node and at the Sun's centre."""

import numpy as np
import pytest

from stellarforge import opacity

TABLE = """fixed metal distribution -- test
    form     version        X           Z          logRs    logR_min    logR_max       logTs    logT_min    logT_max
       1          38    0.700000    0.020000           2   -8.000000   -7.000000           2    3.750000    3.800000

   logT                       logR = logRho - 3*logT + 18
          -8.000  -7.000

   3.750  -0.766  -0.843
   3.800  -0.559  -0.573
"""


def test_parse_table():
    log_t, log_r, log_k = opacity.parse_table(TABLE)
    assert list(log_t) == [3.75, 3.8] and list(log_r) == [-8.0, -7.0]
    assert log_k[1, 0] == -0.559
    with pytest.raises(ValueError):
        opacity.parse_table(TABLE.replace("  -0.573", ""))


needs_tables = pytest.mark.skipif(not opacity.TABLES.exists(),
                                  reason="opacity tables not converted; run `make data`")


@needs_tables
def test_grid_node_returns_the_table_value():
    """X = 0.7, Z = 0.02 is a table; log T 6.0, log R -3.0 is one of its nodes (log rho = -3 in
    g/cm^3). The table there is OPAL's."""
    data = np.load(opacity.TABLES)
    i = np.searchsorted(data["opal_z"], 0.02)
    j = np.searchsorted(data["opal_x"], 0.7)
    k = np.searchsorted(data["opal_log_t"], 6.0)
    m = np.searchsorted(data["opal_log_r"], -3.0)
    expected = 0.1 * 10 ** data["opal_log_kappa"][i, j, k, m]
    assert opacity.Opacity(0.7, 0.02)(1.0, 1e6) == pytest.approx(expected, rel=1e-9)


@needs_tables
def test_sun_centre_and_range():
    kappa = opacity.Opacity(0.7154, 0.0143)
    assert 1.0 < kappa(1.5e5, 1.57e7) * 10 < 2.0   # cm^2/g at the Sun's centre today
    with pytest.raises(ValueError):
        kappa(1e-20, 1e6)                        # below the tables' density range: no extrapolation
