"""evolution.py on a small synthetic grid (logic), then on the real MIST grid when it is converted
(the Phase 1 scientific checks; numbers from the build plan's Validation table)."""

import numpy as np
import pytest

from stellarforge import evolution, mist
from stellarforge.colour import temperature_to_rgb
from stellarforge.evolution import Grid, Star, build_track

COLS = ("age_yr", "mass_msun", "log_l_lsun", "log_teff_k", "phase")


def synthetic_grid(endings=None) -> Grid:
    """2 [Fe/H] x 3 masses; each track's log L is log mass + [Fe/H], so blends are checkable."""
    fehs, masses = np.array([-1.0, 0.0]), np.array([1.0, 2.0, 4.0])
    rows = 5
    data = []
    for f in fehs:
        block = np.zeros((3, rows, len(COLS)), dtype=np.float32)
        for i, m in enumerate(masses):
            block[i, :, 0] = np.arange(rows) * 1e9 / m
            block[i, :, 1] = m
            block[i, :, 2] = np.log10(m) + f + np.arange(rows) * 0.1
            block[i, :, 3] = 3.76
            block[i, :, 4] = [-1, 0, 0, 2, 2]
        data.append(block)
    ending = endings if endings is not None else np.full((2, 3), "white-dwarf cooling sequence")
    return Grid(fehs=fehs, masses_msun=masses, columns=COLS, data=tuple(data),
                age_yr=tuple(d[:, :, 0].astype(float) for d in data),
                star_type=np.full((2, 3), "low-mass"),
                n_rows=np.full((2, 3), rows), ending=np.array(ending), version="1.2")


def test_grid_point_is_published():
    t = build_track(2.0, 0.0, synthetic_grid())
    assert (t.provenance, t.method, t.flags) == ("published", "MIST grid track", [])
    assert t.values["log_l_lsun"][0] == pytest.approx(np.log10(2.0))


def test_interpolates_in_log_mass_and_feh():
    t = build_track(np.sqrt(2.0), -0.5, synthetic_grid())
    assert t.provenance == "interpolated"
    assert t.values["log_l_lsun"][0] == pytest.approx(0.5 * np.log10(2.0) - 0.5, abs=1e-6)
    assert list(t.values["phase"]) == [-1, 0, 0, 2, 2]


def test_never_blends_tracks_that_end_differently():
    endings = np.full((2, 3), "white-dwarf cooling sequence", dtype=object)
    endings[1, 1] = "post-AGB"
    t = build_track(1.9, -0.1, synthetic_grid(endings.astype(str)))
    assert t.provenance == "substituted"
    assert t.method == ("nearest MIST track: 2 M☉, [Fe/H] +0.00; 0.022 dex away in log mass, "
                        "0.10 in [Fe/H]")
    assert "nearest_track_used" in t.flags
    assert "track_incomplete: stops at post-AGB" in t.flags


def test_refuses_to_extrapolate():
    with pytest.raises(ValueError, match="outside the MIST grid"):
        build_track(5.0, 0.0, synthetic_grid())
    with pytest.raises(ValueError, match="outside the MIST grid"):
        build_track(1.0, 0.3, synthetic_grid())


def test_star_at_age_and_phases():
    star = Star(1.0, 0.0, synthetic_grid())
    assert star.at(1.5e9)["log_l_lsun"] == pytest.approx(0.15)
    assert star.at(1.5e9)["phase"] == 0
    with pytest.raises(ValueError):
        star.at(9e9)
    assert [p[0] for p in star.phases()] == [
        "pre-main sequence", "main sequence", "red giant branch"]
    assert star.phases()[1][1:] == (1e9, 3e9)


def test_colour_port_matches_aion_forge_expectations():
    # Expected behaviour from Aion Forge's src/__tests__/starColour.test.ts, read as text.
    r, g, b = temperature_to_rgb(30_000)
    assert b == 1 and r < 0.7 and r < g < r + 0.2
    r3, _, b3 = temperature_to_rgb(3000)
    assert r3 == 1 and b3 < 0.6
    assert temperature_to_rgb(10_000)[0] <= temperature_to_rgb(5772)[0]
    assert temperature_to_rgb([3000, 5772]).shape == (2, 3)


# ---- Scientific checks on the converted MIST grid -------------------------------------------

try:
    GRID = evolution.load_grid()
except FileNotFoundError:
    GRID = None
needs_grid = pytest.mark.skipif(GRID is None, reason="MIST grid not converted; run `make data`")


@needs_grid
def test_sun_at_4_57_gyr():
    # Build plan Validation, re-aimed 11 Nov 2026: L 0.95-1.12 L☉, R 1.00 ± 0.05 R☉,
    # Teff 5712-5872 K (IAU nominal Sun, Prša et al. 2016). MIST's released [Fe/H] = 0 tracks start
    # with Y 0.2703, Z 0.0143, not the calibrated solar model's Y 0.2612, Z 0.0150 (Choi et al.
    # 2016, table 2), so the grid's Sun is brighter and hotter (L 1.106, Teff 5848 K). The ranges
    # allow that known offset upwards only; anything else still fails.
    sun = Star(1.0, 0.0, GRID).at(4.57e9)
    assert 0.95 <= 10 ** sun["log_l_lsun"] <= 1.12
    assert 10 ** sun["log_r_rsun"] == pytest.approx(1.0, abs=0.05)
    assert 5712 <= 10 ** sun["log_teff_k"] <= 5872
    assert PHASE_AT(sun) == "main sequence"


def PHASE_AT(point):
    return mist.PHASE_NAMES[int(point["phase"])]


@needs_grid
def test_metallicity_trend_at_one_solar_mass():
    # Lower [Fe/H]: hotter, brighter, shorter main sequence (MIST; build plan Validation).
    def zams_and_ms_end(feh):
        v = Star(1.0, feh, GRID).track().values
        return v["log_l_lsun"][201], v["log_teff_k"][201], v["age_yr"][453]
    poor, solar = zams_and_ms_end(-1.0), zams_and_ms_end(0.0)
    assert poor[0] > solar[0] and poor[1] > solar[1] and poor[2] < solar[2]


@needs_grid
def test_massive_stars_have_no_agb():
    # MIST reuses its low-mass phase numbers on high-mass tracks (Choi et al. 2016, fig. 12)
    names = [p[0] for p in Star(20.0, 0.0, GRID).phases()]
    assert not any("AGB" in n or "red giant" in n for n in names), names
    assert "AGB" in " ".join(p[0] for p in Star(3.0, 0.0, GRID).phases())


@needs_grid
def test_interpolated_track_is_monotonic_in_age():
    age = Star(1.234, -0.37, GRID).track().values["age_yr"]
    assert np.all(np.diff(age) > 0)


def test_wide_check_is_exact_on_a_linear_grid():
    # Every column linear in log mass and [Fe/H]: the leave-one-out rebuild must be exact
    cols = ("age_yr", "mass_msun", "log_l_lsun", "log_teff_k", "log_r_rsun", "he_core_mass_msun",
            "c_core_mass_msun", "phase")
    fehs, masses, rows = np.array([-1.0, -0.75, 0.0]), np.array([1.0, 2.0, 8.0]), 460
    eep = np.arange(1, rows + 1)
    # Age grows with EEP; the other columns are flat along the track
    shape = np.column_stack([eep * 1e7, *np.ones((6, rows)), np.zeros(rows)]) * [1, 1, 1, 1, 1,
                                                                                  0.5, 0.4, 1]
    data = [np.array([(2 + np.log10(m) + f) * shape for m in masses]) for f in fehs]
    grid = Grid(fehs=fehs, masses_msun=masses, columns=cols, data=tuple(data),
                age_yr=tuple(d[:, :, 0] for d in data), star_type=np.full((3, 3), "high-mass"),
                n_rows=np.full((3, 3), rows), ending=np.full((3, 3), evolution.CARBON_END),
                version="1.2")
    errs = evolution.wide_check(grid)
    stages = {stage for _, stage, _ in errs}
    assert stages == {"main sequence", "after the main sequence", "end of the track"}
    assert max(max(e) for e in errs.values()) < 1e-9
