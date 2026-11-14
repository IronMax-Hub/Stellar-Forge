"""Phase 6: planets through their star's life. Ports are checked against Aion Forge's own test
values (read as text); the physics against the papers; the reference cases against the build plan's
Validation table, with what fails recorded there rather than loosened here."""

import numpy as np
import pytest

from stellarforge import evolution
from stellarforge.export import _orbit_knots
from stellarforge.planets import coevolution as co
from stellarforge.planets import escape, shoreline, xuv


def test_kopparapu_edges_for_the_sun():
    # Kopparapu et al. 2013, Table 3 at 5780 K: d = (1 / S_eff☉)^½
    assert co.habitable_edge_au("runaway greenhouse", 1.0, 5780) == pytest.approx(0.9753, abs=1e-4)
    assert co.habitable_edge_au("moist greenhouse", 1.0, 5780) == pytest.approx(0.9931, abs=1e-4)
    assert co.habitable_edge_au("maximum greenhouse", 1.0, 5780) == pytest.approx(1.7055, abs=1e-4)
    assert np.isnan(co.habitable_edge_au("runaway greenhouse", 1.0, 7300))   # outside 2,600-7,200 K
    assert np.isnan(co.habitable_edge_au("runaway greenhouse", 1.0, 2500))


def test_xuv_port_matches_aion_forge_tests():
    # Expected values from Aion Forge's src/__tests__/xuv.test.ts
    assert xuv.xuv_share(5772, 4.6e9, None) == pytest.approx(3.4e-6, rel=1e-9)
    assert xuv.saturation_time_gyr(5772) == 0.1
    assert xuv.saturation_time_gyr(3900) == pytest.approx(0.8, abs=1e-12)
    assert xuv.saturation_time_gyr(2700) == 8 and xuv.saturation_time_gyr(2000) == 8
    assert xuv.activity(1, 2) == pytest.approx(2**-1.23, abs=1e-12)
    assert xuv.activity(1, 0.5) == 1
    assert xuv.photospheric_share(10000) > 1e-4 and xuv.photospheric_share(3000) < 1e-12
    # Held at the main-sequence-end value afterwards
    assert xuv.xuv_share(5772, 12e9, 10e9) == xuv.xuv_share(5772, 10e9, 10e9)


def test_shoreline_port_matches_aion_forge_tests():
    # Aion Forge's src/__tests__/atmosphericEscape.test.ts: the reference Sun's dose falls as 1/a²
    def keeps(v_esc, a_au):
        return float(shoreline.air_retained(1 / a_au**2, v_esc))
    assert shoreline.critical_dose(11.2) == 10
    assert keeps(11.2, 1) == pytest.approx(0.99, abs=0.005)      # Earth
    assert keeps(10.4, 0.72) == pytest.approx(0.93, abs=0.005)   # Venus
    assert keeps(2.64, 9.5) == pytest.approx(0.87, abs=0.005)    # Titan-like
    assert keeps(5.0, 1.52) == 0 and keeps(4.3, 0.39) == 0       # Mars, Mercury


def test_energy_limited_rate_by_hand():
    # Owen & Wu eq. 19 worked by hand: R_p = 2 R⊕, M_p = 5 M⊕, a = 1 AU, L_HE = 10⁻⁴ L☉, η = 0.1
    # 0.1 π (1.2742e9 cm)³ 3.828e29 / (4π (1.496e13)² 6.674e-8 × 2.986e28) = 4.44e7 g/s
    assert escape.mass_loss_g_s(2.0, 5.0, 1.0, 1e-4) == pytest.approx(4.44e7, rel=2e-3)


def test_owen_wu_radius_doubles_at_x2():
    x2 = escape.x2(10, 1.0, 1e8, 5.0)
    assert x2 == pytest.approx(0.027)                        # eq. 17 at its reference values
    r, valid = escape.radius_rearth(5.0, 5.0 * x2, 10, 1.0, 1e8)
    assert valid and r == pytest.approx(2 * 5**0.25)
    _, valid = escape.radius_rearth(5.0, 6.0, 10, 1.0, 1e8)     # X ≥ 1: Chen & Kipping instead
    assert not valid


def test_supernova_rule():
    # Hills 1983: a circular orbit is unbound once more than half the mass goes at once
    assert co.supernova_unbinds(10.0, 4.9) and not co.supernova_unbinds(10.0, 5.1)


def test_eccentric_tides_reduce_to_the_circular_case():
    # Mustill & Villaver 2012 eqs. 1, 4, 5 at e = 0: ȧ/a = -(2 f₂ / 9 t_conv)(M_env/M★) q (1+q) (R★/a)⁸
    a, mp, ms, menv, r, lum = np.array([1.5, 2.0, 3.0]), 1e-3, 0.8, 0.5, 1.0, 2000.0
    ra, _ = co.tide_rates_per_yr(a, 0 * a, mp, ms, menv, r, lum)
    t_conv = (menv * co.MSUN_G * (r * co.AU_CM) ** 2 / (3 * lum * co.L_SUN_ERG_S)) ** (1 / 3)
    f2 = 4.5 * np.minimum(1, (co._period_s(a, ms + mp) / (2 * t_conv)) ** 2)
    q = mp / ms
    circular = -(2 * f2 / (9 * t_conv)) * (menv / ms) * q * (1 + q) * (r / a) ** 8 * co.YEAR_S
    assert np.allclose(ra, circular, rtol=1e-12)
    # The sub-stepped integration against Phase 6's closed form a⁸ - 8 K dt (drag negligible at 3 R★)
    k = -ra[2] * 3.0**8                   # ȧ a⁷ = -K, constant while f₂ is saturated
    assert f2[2] == 4.5
    dt = 0.3 * 3.0**8 / (8 * k)            # 30% of the way to a = 0
    a1, e1, _, drag = co._orbit_decay(np.array([3.0]), np.zeros(1), np.array([mp]), dt, ms, menv,
                                      r, lum)
    assert a1[0] == pytest.approx((3.0**8 - 8 * k * dt) ** 0.125, rel=1e-4)
    assert e1[0] == 0 and drag[0] < 1e-6


def test_tides_circularise():
    # ė < 0 for every e > 0, across saturated and unsaturated f_i (fiducial parameters)
    for lum in (10.0, 1e3, 1e5):
        for a in (1.2, 2.0, 5.0, 20.0):
            _, re = co.tide_rates_per_yr(a, np.linspace(0.01, 0.9, 20), 1e-3, 1.0, 0.6, 1.0, lum)
            assert np.all(re < 0)


def test_drag_by_hand():
    # Schröder & Connon Smith 2008 §4.2: tip-RGB Sun of 0.668 M☉ and 256 R☉ = 1.2 AU; today's
    # chromosphere scaled to a gravity 4.7 dex lower gives 2 × 10¹² cm⁻³, ρ ≈ 4 × 10⁻⁹ kg m⁻³ at
    # 0.03 AU, and a decay time of about 14 Myr for Earth there (λ_d = 3, c_s = 8 km/s)
    rho = co.chromosphere_density_g_cm3(0.03, co.G_SUN_CGS * 10**-4.7)
    assert rho == pytest.approx(4e-12, rel=0.15)
    tau = co.drag_decay_time_yr(1.2 + 0.03, 3.0035e-6, 0.668, 4e-12)
    assert 9e6 < tau < 18e6               # 11.1 Myr; the Validation table holds the comparison


def test_habitable_zone_flicker_is_dropped():
    ev = [{"age_yr": 1e9, "kind": "enters habitable zone", "detail": ""},
          {"age_yr": 5e9, "kind": "leaves habitable zone", "detail": ""},
          {"age_yr": 5.001e9, "kind": "enters habitable zone", "detail": ""},
          {"age_yr": 5.002e9, "kind": "leaves habitable zone", "detail": ""},
          {"age_yr": 6e9, "kind": "engulfed", "detail": ""}]
    assert [e["age_yr"] for e in co._debounce(ev)] == [1e9, 5.002e9, 6e9]


def test_orbit_knots_keep_ends_of_flat_runs():
    a = np.array([1.0, 1.0, 1.0, 1.2, 1.5, 1.5, 1.5, np.nan, np.nan])
    idx, vals, ecc = _orbit_knots(a)
    assert idx == [0, 2, 3, 4, 6] and vals == [1.0, 1.0, 1.2, 1.5, 1.5] and ecc == [0.0] * 5
    assert np.allclose(np.interp(range(7), idx, vals), a[:7])
    # A change in e alone keeps its knot
    idx, _, ecc = _orbit_knots(np.ones(5), np.array([0.1, 0.1, 0.1, 0.05, 0.05]))
    assert idx == [0, 2, 3, 4] and ecc == [0.1, 0.1, 0.05, 0.05]


# ---- On the MIST grid -----------------------------------------------------------------------

try:
    evolution.load_grid()
    HAVE_GRID = True
except FileNotFoundError:
    HAVE_GRID = False
needs_grid = pytest.mark.skipif(not HAVE_GRID, reason="MIST grid not converted; run `make data`")


@needs_grid
def test_solar_system_reference_case():
    hist, r = co.solar_system()
    fate = dict(zip([p[0] for p in co.SOLAR_SYSTEM], r["fate"]))
    assert [fate[n] for n in ("Mercury", "Venus", "Earth")] == ["engulfed"] * 3
    # Mars: either outcome passes if the closest approach and deciding phase are reported. With
    # its measured e = 0.0935 (Phase 6.1) it survives at 1.04 R★ from pericentre
    mars = 3
    assert r["closest_approach_rstar"][mars] >= 1 and r["deciding_phase"][mars]
    assert r["initial_e"][mars] == pytest.approx(0.0935)
    assert all(fate[n] == "orbits white dwarf" for n in ("Jupiter", "Saturn", "Uranus", "Neptune"))
    # Widening is M★,0 / M_WD for the outer planets (no tide reaches them). The plan's 1.76-1.84×
    # assumed a 0.544-0.569 M☉ white dwarf; MIST's is 0.540 M☉, so this gives 1.852 and the
    # Validation table records that check as failed.
    widening = r["final_a_au"][4:] / np.array([p[2] for p in co.SOLAR_SYSTEM[4:]])
    assert widening == pytest.approx(hist.mass_msun[0] / hist.mass_msun[-1], rel=1e-3)


@needs_grid
def test_slow_mass_loss_keeps_e():
    # Veras et al. 2011: adiabatic mass loss keeps e; no tide reaches Uranus and Neptune
    _, r = co.solar_system()
    assert np.allclose(r["final_e"][6:], r["initial_e"][6:], atol=1e-6)
    assert np.all(r["final_e"][:4][r["fate"][:4] == "orbits white dwarf"] <= r["initial_e"][:4][
        r["fate"][:4] == "orbits white dwarf"])


@needs_grid
def test_innermost_agb_survivors():
    # Mustill & Villaver 2012 find the innermost Jovian survivors leaving the AGB at about 2 AU
    # (1 M☉) and 10 AU (5 M☉) with Vassiliadis & Wood models. On MIST: 3.65 and 13.9 AU
    # (regression bands; the Validation table holds the comparison)
    for m, grid, band in ((1.0, np.arange(1.0, 6.01, 0.1), (3.0, 4.5)),
                          (5.0, np.arange(3.0, 25.01, 0.25), (11.0, 17.0))):
        hist = co.star_history(evolution.build_track(m, 0.0))
        r = co.evolve_planets(hist, grid, [317.8] * len(grid), [0.9] * len(grid),
                              [True] * len(grid), 3e6)
        first = np.flatnonzero(r["fate"] != "engulfed")[0]
        assert band[0] < r["final_a_au"][first] < band[1]


@needs_grid
def test_earth_and_the_habitable_zone():
    t = co.earth_habitable_zone_timing()
    # MIST's Sun is already 1.106 L☉ at 4.57 Gyr, so both inner edges are past 1 AU "today"
    assert t["runaway greenhouse"]["edge_at_4_57_au"] > 1
    # Counted from MIST's 1 L☉ moment (regression bands; the Validation table holds the target)
    assert 0.15 < t["moist greenhouse"]["after_1_lsun_gyr"] < 0.3
    assert 0.5 < t["runaway greenhouse"]["after_1_lsun_gyr"] < 0.8


@needs_grid
def test_shoreline_labels_in_the_solar_system():
    _, r = co.solar_system()
    crossed = dict(zip([p[0] for p in co.SOLAR_SYSTEM], r["shoreline_crossed"]))
    assert crossed["Mercury"] and not crossed["Venus"] and not crossed["Earth"]
    # With Aion Forge's K = 10 Mars lands on the airless side (its own test expects that); the
    # build plan's check wants it on the side with air, and is recorded as failed.
    assert crossed["Mars"]


@needs_grid
def test_close_sub_neptune_is_stripped_and_far_one_is_not():
    hist = co.star_history(evolution.build_track(1.0, 0.0))
    r = co.evolve_planets(hist, [0.05, 1.0], [6.0, 6.0], [0.03, 0.03], [False, False], 3e6)
    assert r["final_class"][0] == "super-Earth" and r["final_f_env"][0] < 0.01
    assert r["final_f_env"][1] > 0.02
    assert any(e["kind"] == "class changed" for e in r["events"][0])
