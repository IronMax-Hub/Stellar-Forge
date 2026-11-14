"""planets/: the Ida & Lin formulae against the papers' closed forms and stated values, and the
classifier (build plan, Phase 5 Validation)."""

import numpy as np
import pytest

from stellarforge.planets import classify, disk, growth, migration, population


def test_disk_scalings():
    assert disk.sigma_dust(1.0, 1.0, 2.7) == pytest.approx(10.0)          # eq. 11 at 1 AU
    assert disk.sigma_dust(4.0, 1.0, 2.7) == pytest.approx(10 * 4.2 / 8)  # beyond the snow line
    assert disk.sigma_gas(1.0, 1.0) == pytest.approx(2.4e3)               # eq. 12
    assert disk.f_dust(1.0, 0.3) == pytest.approx(10**0.3)                # f_d = f_g 10^[Fe/H]
    assert disk.gas_factor(2.0, 1e7, 1e7) == pytest.approx(2 / np.e)      # eq. 49
    assert disk.snow_line_au(1.0) == 2.7 and disk.snow_line_au(0.5) == pytest.approx(0.675)
    # eq. 15 is where eq. 14 gives 170 K (with L ∝ M⁴): 2.7 AU for the Sun
    assert disk.temperature_k(2.7) == pytest.approx(170, abs=1)


@pytest.mark.parametrize("a", [0.5, 1.0, 5.0, 20.0])
def test_isolation_masses_match_the_closed_forms(a):
    eta = 4.2 if a > 2.7 else 1.0
    sd = disk.sigma_dust(a, 1.0, 2.7)
    assert growth.isolation_mass(sd, a) == pytest.approx(0.16 * eta**1.5 * a**0.75)      # eq. 21
    assert growth.no_isolation_mass(sd, a) == pytest.approx(1.2 * eta * a**0.5)          # eq. 23
    assert growth.gas_isolation_mass(disk.sigma_gas(a, 1.0), a) == pytest.approx(50 * a**0.75)


def test_gas_capture_scalings():
    assert growth.critical_core_mass(1e-6) == pytest.approx(10.0)                        # eq. 33
    # M_c,KH: τ_KH = τ_disk = 10⁷ yr at 4.6 M⊕ (eq. 31)
    assert (1e9 / 1e7) ** (1 / 3) == pytest.approx(4.6, abs=0.05)
    assert growth.kelvin_helmholtz_time_yr(4.6416) == pytest.approx(1e7, rel=1e-3)
    assert growth.gap_opening_mass(1.0) == pytest.approx(120, rel=0.06)                  # eq. 38
    assert growth.disk_gas_mass_limit(1.0, 4.0) == pytest.approx(580)                    # eq. 47
    # eq. 18 at 1 AU for 1 M⊕ in the f_d = f_g = 1 disk
    assert growth.core_accretion_time_yr(1, 1, 1, 1, 1) == pytest.approx(1.2e5)


def test_migration():
    # Type I for an Earth mass at 1 AU in the f_g = 1 disk takes ~10⁵ yr at C1 = 1, inward
    rate = migration.type1_rate(1.0, 1.0, 1.0, c1=1.0)
    assert rate < 0 and 1 / abs(rate) == pytest.approx(1.0e5, rel=0.05)
    assert migration.type1_rate(1.0, 1.0, 1.0, c1=0.1) == pytest.approx(0.1 * rate)
    assert migration.type1_rate(1.0, 1.0, 1.0, p=3.0) > 0       # outward above p = 2.92 (q = -1/2)
    # Type II: eq. 65 for a Jupiter mass at 1 AU, f_g = 1, α = 10⁻³: 8 × 10⁴ yr, inward inside R_m
    rate = migration.type2_rate(1.0, 317.83, 1.0, 0.0, 1e7)
    assert rate == pytest.approx(-1 / 8e4)
    assert migration.type2_rate(20.0, 317.83, 1.0, 0.0, 1e7) > 0                # beyond R_m = 10 AU
    # ...and never faster than the gas: eq. 70 for a light planet in a massive disk
    assert migration.type2_rate(1.0, 10.0, 30.0, 0.0, 1e7) == pytest.approx(-1 / 4.3e4)


def test_classes_at_their_boundaries():
    cl = classify.classify
    assert cl(300, 0.5, False) == "gas giant"
    assert cl(300, 0.4999, False) == "sub-Neptune"
    assert cl(10, 0.01, True) == "ice giant" and cl(9.99, 0.2, True) == "sub-Neptune"
    assert cl(15, 0.2, False) == "sub-Neptune"
    assert cl(2, 0.0099, False) == "super-Earth" and cl(1.99, 0.0, False) == "terrestrial"
    assert cl(3, 0.0, True) == "super-Earth"       # ice-rich super-Earths stay super-Earths
    with pytest.raises(ValueError):
        cl(1.0, 1.5, False)


def test_every_planet_gets_exactly_one_class():
    rng = np.random.default_rng(1)
    m = 10 ** rng.uniform(-2, 3.5, 10_000)
    f = rng.uniform(0, 1, 10_000) ** 3
    ice = rng.random(10_000) < 0.5
    classes = classify.classify(m, f, ice)
    assert set(classes) <= set(classify.CLASSES) and len(classes) == 10_000


# Masses (M⊕) from Guillot 2005, section 3.1. Envelope fractions bracket the published ranges:
# Jupiter 10-42 M⊕ of heavy elements, Saturn ~20 M⊕ (Guillot 2005, sections 3.3 and 5); Uranus
# 0.5-4.2 M⊕ and Neptune 0.5-3.2 M⊕ of hydrogen and helium (Guillot 2005 section 3.4, citing
# Podolak et al. 2000); the terrestrial planets have no hydrogen-helium envelope.
SOLAR_SYSTEM = {
    "Mercury": (0.0553, (0.0,), False, "terrestrial"),
    "Venus": (0.815, (0.0,), False, "terrestrial"),
    "Earth": (1.0, (0.0,), False, "terrestrial"),
    "Mars": (0.107, (0.0,), False, "terrestrial"),
    "Jupiter": (317.834, (1 - 42 / 317.834, 1 - 10 / 317.834), False, "gas giant"),
    "Saturn": (95.161, (1 - 20 / 95.161,), False, "gas giant"),
    "Uranus": (14.538, (0.5 / 14.538, 4.2 / 14.538), True, "ice giant"),
    "Neptune": (17.148, (0.5 / 17.148, 3.2 / 17.148), True, "ice giant"),
}


@pytest.mark.parametrize("name", SOLAR_SYSTEM)
def test_solar_system(name):
    mass, envelopes, ice, expected = SOLAR_SYSTEM[name]
    for f in envelopes:   # both ends of the published range give the same class
        assert classify.classify(mass, f, ice) == expected, (name, f)


# ---- Part B: the population integrator ------------------------------------------------------

def _disk(a_au, f_g0=1.0, feh=0.0, tau=3e6):
    a = np.atleast_2d(np.asarray(a_au, float))
    n = len(a)
    return {"f_g0": np.full(n, f_g0), "f_d0": np.full(n, f_g0 * 10**feh),
            "tau_disk_yr": np.full(n, tau), "a0_au": a}


def test_annuli_share_the_disk_solids():
    a = np.array([[0.1, 0.7, 3.0, 20.0]])
    f_d = np.array([2.0])
    whole = population.annulus_solids(np.array([[1.0]]), f_d, 2.7)
    assert population.annulus_solids(a, f_d, 2.7).sum() == pytest.approx(whole[0, 0])
    # MMSN solids 0.05-50 AU: 4π Σ0 AU² (√2.7 - √0.05 + 4.2 (√50 - √2.7)) ≈ 114 M⊕ (eq. 11)
    assert whole[0, 0] == pytest.approx(2 * 114.0, rel=0.01)


def test_inner_core_stops_at_its_isolation_mass():
    state = population.evolve(_disk([[0.3, 1.0, 3.5]], tau=1e7), 1.0)
    iso = growth.isolation_mass(disk.sigma_dust(1.0, 1.0, 2.7), 1.0)   # eq. 20: 0.16 M⊕
    assert state["core_mearth"][0, 1] == pytest.approx(iso, rel=0.01)   # type I moved it a little
    assert state["env_mearth"][0, 1] / state["core_mearth"][0, 1] < 0.01
    assert not state["ice_rich"][0, 1] and state["ice_rich"][0, 2]


def test_rich_outer_disk_makes_a_migrating_giant():
    state = population.evolve(_disk([[8.0]], f_g0=3.0, feh=0.3, tau=5e6), 1.0)
    m = state["core_mearth"][0, 0] + state["env_mearth"][0, 0]
    assert state["env_mearth"][0, 0] / m > 0.5 and m > 100
    assert m <= growth.gap_opening_mass(state["a_form_au"][0, 0])   # eq. 38 truncates the gas
    assert state["a_au"][0, 0] < 8.0                                 # and it migrated inwards


def test_population_is_reproducible_and_step_converged():
    a = population.run_cell(1.0, 0.0, 400, seed=11)
    b = population.run_cell(1.0, 0.0, 400, seed=11)
    assert np.array_equal(a["planets"]["mass_mearth"], b["planets"]["mass_mearth"])

    def giant_hosts(cell):
        p = cell["planets"]
        return np.unique(p["system"][p["class"] == "gas giant"]).size / cell["n_systems"]
    coarse = giant_hosts(population.run_cell(1.0, 0.0, 1500, seed=5, steps_per_dex=40))
    fine = giant_hosts(population.run_cell(1.0, 0.0, 1500, seed=5, steps_per_dex=200))
    assert abs(coarse - fine) < 0.02


def test_inner_edge_merge_keeps_the_mass():
    state = {"core_mearth": np.array([[1.0, 2.0, 3.0]]), "env_mearth": np.array([[0.0, 5.0, 0.0]]),
             "a_au": np.array([[0.04, 0.04, 1.0]]), "a_form_au": np.array([[0.5, 4.0, 1.0]]),
             "ice_rich": np.array([[False, True, False]]), "a_ice_au": 2.7}
    out = population.merge_inner_edge(state)
    assert out["core_mearth"].sum() == 6.0 and out["env_mearth"].sum() == 5.0
    assert out["core_mearth"][0, 1] == 3.0 and out["ice_rich"][0, 1]   # the heavier one stays


def test_giants_need_metals():
    def hosts(feh):
        p = population.run_cell(1.0, feh, 800, seed=2)["planets"]
        return np.unique(p["system"][p["class"] == "gas giant"]).size
    assert hosts(-2.0) == 0
    assert hosts(-0.5) < hosts(0.0) < hosts(0.5)


def test_chen_kipping_radii():
    from stellarforge.planets import radius
    assert radius.radius_rearth(1.0) == pytest.approx(1.008)                 # Table 1 constant
    for m in (2.04, 131.6):                                                  # segments meet
        below, above = radius.radius_rearth([m * (1 - 1e-9), m * (1 + 1e-9)])
        assert below == pytest.approx(above, rel=1e-3)
    # A Jupiter mass gives 13.8 R⊕, above Jupiter's 11.2: the fit includes inflated hot Jupiters
    assert radius.radius_rearth(317.83) == pytest.approx(13.8, rel=0.01)
    with pytest.raises(ValueError):
        radius.radius_rearth(0.0)
