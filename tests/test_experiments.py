"""experiments.py: the IMF sampler against the Kroupa 2001 integrals, byte-identical reruns, and the
Phase 3 metallicity checks on the converted MIST grid (build plan, Validation)."""

import numpy as np
import pytest

from stellarforge import evolution, experiments

LO, HI = experiments.IMF_RANGE_MSUN
BRK, (A1, A2) = experiments.KROUPA_BREAK_MSUN, experiments.KROUPA_ALPHAS


def kroupa_integral(a, b, power):
    """∫ m^power ξ(m) dm over [a, b] for the Kroupa IMF, continuous at the break (unnormalised)."""
    def seg(lo, hi, alpha, scale):
        if hi <= lo:
            return 0.0
        e = power - alpha + 1
        return scale * (hi ** e - lo ** e) / e
    return seg(max(a, LO), min(b, BRK), A1, 1.0) + seg(max(a, BRK), min(b, HI), A2, BRK ** (A2 - A1))


def test_imf_share_above_8_msun():
    # Build plan Validation: 0.71% of stars by number above 8 M☉ (Kroupa IMF, 0.1-100 M☉), about 11
    # such stars per 1,000 M☉ formed.
    share = kroupa_integral(8, HI, 0) / kroupa_integral(LO, HI, 0)
    per_1000 = 1000 * kroupa_integral(8, HI, 0) / kroupa_integral(LO, HI, 1)
    assert share == pytest.approx(0.0071, abs=0.00005)
    assert per_1000 == pytest.approx(11, abs=0.5)
    stars = experiments.kroupa_sample(1_000_000, 12345)
    assert LO <= stars.min() and stars.max() <= HI
    n = len(stars)
    # Within 4 standard deviations of the binomial count
    assert abs(np.mean(stars > 8) - share) < 4 * np.sqrt(share * (1 - share) / n)
    assert np.mean(stars) == pytest.approx(kroupa_integral(LO, HI, 1) / kroupa_integral(LO, HI, 0),
                                           rel=0.01)


def test_sampler_is_seeded():
    assert np.array_equal(experiments.kroupa_sample(1000, 7), experiments.kroupa_sample(1000, 7))
    assert not np.array_equal(experiments.kroupa_sample(1000, 7), experiments.kroupa_sample(1000, 8))


def test_bad_options_are_refused():
    with pytest.raises(SystemExit):
        experiments.parse(["lifetime-map", "--colour=red"])
    with pytest.raises(SystemExit):
        experiments.parse(["no-such-experiment"])
    assert experiments.parse(["all", "--masses=10", "--export"])[2] is True


# ---- On the converted MIST grid -------------------------------------------------------------

needs_grid = pytest.mark.skipif(not list(evolution.GRIDS.glob("*.npz")),
                                reason="MIST grid not converted; run `make data`")


@needs_grid
def test_reruns_are_byte_identical(tmp_path, monkeypatch):
    # Build plan Validation: the same command gives a byte-identical result.json
    monkeypatch.setattr(experiments, "RESULTS", tmp_path)
    params = {**experiments.DEFAULTS, "feh": "-1:0:0.5", "masses": 15, "stars": 20_000}
    for name in ("population", "remnant-map"):
        first = experiments.run(name, params)
        experiments.sweep.cache_clear()   # recompute, do not reuse the first run's sweep
        second = experiments.run(name, params)
        assert first != second
        assert (first / "result.json").read_bytes() == (second / "result.json").read_bytes()
        assert (first / "figure.png").exists() and (first / "run.json").exists()


def _sweep(fehs):
    return dict(zip(fehs, experiments.sweep(experiments.mass_grid(200), fehs)))


@needs_grid
def test_total_lifetime_wherever_the_track_ends_finally():
    # Tracks that reach the end of carbon burning without a MIST core mass still have a lifetime
    s = _sweep((-3.0, -1.0))
    for cells in s.values():
        for c in cells:
            final = c["ending"] in evolution.FINAL_ENDINGS or c["ending"].startswith(
                evolution.CARBON_END)
            assert final == (not np.isnan(c["total_lifetime_yr"])), (c["mass"], c["ending"])
    assert any(c["ending"] == evolution.NO_CO_CORE for cells in s.values() for c in cells)


@needs_grid
def test_shorter_main_sequence_at_low_metallicity():
    # Below 8 M☉ every star's main sequence is shorter at [Fe/H] -2 than at 0. Above ~8.7 M☉ MIST's
    # rotating stars live up to ~30% longer at low metallicity: rotational mixing is stronger there
    # (Choi et al. 2016, fig. 20); reported as a result in the build plan's Validation.
    s = _sweep((-2.0, 0.0))
    pairs = [(a["ms_lifetime_yr"], b["ms_lifetime_yr"]) for a, b in zip(s[-2.0], s[0.0])
             if a["mass"] < 8 and not np.isnan(a["ms_lifetime_yr"] + b["ms_lifetime_yr"])]
    assert len(pairs) > 100
    assert all(poor < rich for poor, rich in pairs)


@needs_grid
def test_remnants_against_metallicity():
    # Build plan Validation (Heger et al. 2003): final helium cores, and black holes below the gap,
    # grow as metallicity falls, where winds are weaker. Medians over 20-100 M☉ stars whose tracks
    # reach carbon burning; below [Fe/H] about -1.5 winds are already weak and the medians level off.
    fehs = experiments.feh_grid("-4:0.5:0.5")
    s = _sweep(fehs)
    he, bh = [], []
    for f in fehs:
        cells = s[f]
        he.append(np.median([c["he_core"] for c in cells if 20 <= c["mass"] <= 100
                             and c["ending"].startswith(evolution.CARBON_END)
                             and not np.isnan(c["he_core"])]))
        bh.append(np.median([c["remnant_mass"] for c in cells
                             if c["remnant"] == "black hole" and c["he_core"] < 65]))
    poor, rich = np.array(fehs) <= -1.5, np.array(fehs) >= 0
    assert min(np.array(he)[poor]) > max(np.array(he)[rich])
    assert min(np.array(bh)[poor]) > max(np.array(bh)[rich])


@needs_grid
def test_population_takes_the_nearest_swept_mass():
    # Each star takes the remnant of the nearest swept mass in log mass; recount by brute force
    p = {**experiments.DEFAULTS, "feh": "0:0:1", "masses": 15, "stars": 20_000}
    shares = experiments.population(p)["panels"][0]["rows"]
    masses = np.array([m for m in experiments.mass_grid(15) if m <= HI])
    stars = experiments.kroupa_sample(p["stars"], p["seed"])
    nearest = np.abs(np.log(stars)[:, None] - np.log(masses)[None, :]).argmin(axis=1)
    kinds = np.array([c["remnant"] for c in experiments.sweep(tuple(masses), (0.0,))[0]])
    for row in shares:
        assert row["values"][0] == pytest.approx(100 * np.mean(kinds[nearest] == row["label"]),
                                                 rel=1e-4, abs=1e-9)
    assert sum(r["values"][0] for r in shares) == pytest.approx(100, rel=1e-4)
