"""Contract test: export.py must produce the shape of contract/fixture.json. Shape only, never values."""

import json
from pathlib import Path

import pytest

from stellarforge import SCHEMA_VERSION, evolution, export

FIXTURE = json.loads((Path(__file__).parent.parent / "contract" / "fixture.json").read_text())


# Objects whose keys vary between documents (contract/README.md: "object of ..."); every value must
# match the fixture's value kind.
MAPS = {"inputs", "models", "phase_names", "host_share"}
# Fields that may be null: remnant values with no remnant or no MIST value, a row without y, no seed.
NULLABLE = {"mass_msun", "radius_km", "cooling", "final_mass_msun", "he_core_mass_msun",
            "co_core_mass_msun", "y", "seed", "xi1", "density_concentration", "sun_rho_c_kg_m3",
            "sun_p_c_pa", "sun_t_c_k", "mist"}
# Lists whose items may be null: experiment cells without a number, word or provenance.
NULLABLE_ITEMS = {"values", "labels", "provenance"}
# Blocks a document may carry beside `meta`; the fixture holds them all.
BLOCKS = {"grid", "experiment", "polytropes", "profiles", "population", "systems"}


def kind(value):
    return "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else \
        type(value).__name__


def assert_shape(actual, expected, path="document", key=None):
    """Same keys and value kinds as the fixture, recursively; every list item is checked against
    the fixture's first item."""
    if key in NULLABLE and (actual is None or expected is None):
        return
    if path == "document":
        assert "meta" in actual and set(actual) - {"meta"} and set(actual) <= set(expected), \
            f"document blocks {sorted(actual)}, expected meta and some of {sorted(BLOCKS)}"
        for k in actual:
            assert_shape(actual[k], expected[k], f"document.{k}", k)
        return
    if isinstance(expected, dict) and key in MAPS:
        assert isinstance(actual, dict), path
        kinds = {kind(v) for v in expected.values()}
        assert all(kind(v) in kinds for v in actual.values()), path
    elif isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: {kind(actual)}, expected an object"
        assert set(actual) == set(expected), f"{path}: keys differ by {set(actual) ^ set(expected)}"
        for k in expected:
            assert_shape(actual[k], expected[k], f"{path}.{k}", k)
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: {kind(actual)}, expected a list"
        sample = next((e for e in expected if e is not None), None)
        for i, item in enumerate(actual if sample is not None else []):
            if not (key in NULLABLE_ITEMS and item is None):
                assert_shape(item, sample, f"{path}[{i}]")
    else:
        assert kind(actual) == kind(expected), f"{path}: {kind(actual)}, expected {kind(expected)}"


REMNANT = {
    "type": "neutron star", "mass_msun": 1.4, "radius_km": 12.0, "provenance": "predicted",
    "prescription": "test", "how": "test", "final_mass_msun": 11.0, "he_core_mass_msun": 3.0,
    "co_core_mass_msun": 2.0, "flags": ["test"], "cooling": None,
    "alternative": {"prescription": "test", "type": "neutron star", "mass_msun": 1.3},
}


def exported_document():
    meta = export.build_meta(
        dataset="test", models={"colour": "test"}, inputs={"mass_msun": 2.0, "feh": -0.5},
        reference_keys=["Choi2016"],
    )
    track = export.build_track(
        mass_msun=2.0, feh=-0.5, method="test", provenance="derived", ending="test", flags=["test"],
        phase_names={-1: "pre-main sequence", 0: "main sequence"},
        age_yr=[1, 2], mass_now_msun=[2, 1.9], log_l_lsun=[0, 1], log_teff_k=[3.7, 3.8],
        log_r_rsun=[0, 0.1], phase=[0, 2], rgb=[[1, 1, 1], [1, 0.9, 0.8]],
        remnant=REMNANT,
    )
    grid = export.build_grid(feh=-0.5, feh_values=[-0.5], mass_values_msun=[2.0],
                             files=["f.json"], tracks=[track])
    return export.build_document(meta, grid)


def test_export_matches_fixture_shape():
    assert_shape(exported_document(), FIXTURE)


@pytest.mark.skipif(not list(evolution.GRIDS.glob("*.npz")),
                    reason="MIST grid not converted; run `make data`")
def test_real_web_export_matches_fixture_shape():
    document = export.web_document(0.0)
    assert_shape(document, FIXTURE)
    for track in document["grid"]["tracks"]:
        # Ages are exported unrounded: some MIST points are microseconds apart, and rounding merged
        # them. Ties left are MIST's own (e.g. 2.22 M☉ at [Fe/H] -4.0).
        source = set(evolution.build_track(track["mass_msun"], 0.0).values["age_yr"])
        assert set(track["age_yr"]) <= source, track["mass_msun"]
        assert all(b >= a for a, b in zip(track["age_yr"], track["age_yr"][1:])), track["mass_msun"]


def test_experiment_document_matches_fixture_shape():
    meta = export.build_meta(dataset="test", models={"colour": "test"}, inputs={"feh": 0.0},
                             reference_keys=["Choi2016"])
    heat = export.build_panel(
        title="t", kind="heatmap", x_values=[1, 2], log_x=True,
        rows=[export.build_row(label="0", y=0, values=[1e9, float("nan")],
                               labels=[None, "track incomplete"], provenance=["published", None])])
    table = export.build_panel(title="t", kind="table", columns=["a"],
                               rows=[export.build_row(label="r", values=[1.0])])
    document = export.build_document(meta, experiment=export.build_experiment(
        name="n", title="t", summary="s", panels=[heat, table]))
    assert_shape(document, FIXTURE)
    with pytest.raises(ValueError):
        export.build_panel(title="t", kind="pie", rows=[])
    with pytest.raises(ValueError):
        export.build_panel(title="t", kind="curves", x_values=[1, 2],
                           rows=[export.build_row(label="r", values=[1.0])])


@pytest.mark.skipif(not list(evolution.GRIDS.glob("*.npz")),
                    reason="MIST grid not converted; run `make data`")
def test_real_experiments_match_fixture_shape():
    from stellarforge import experiments
    params = {**experiments.DEFAULTS, "feh": "-1:0:0.5", "masses": 12, "stars": 1000}
    for name in experiments.EXPERIMENTS:
        assert_shape(experiments.result_document(name, params), FIXTURE)


def test_polytrope_document_matches_fixture_shape():
    document = export.polytrope_document()
    assert_shape(document, FIXTURE)
    models = document["polytropes"]["models"]
    assert [m["n"] for m in models] == document["polytropes"]["n_values"]
    for m in models:
        assert m["radius_frac"][0] == 0 and m["radius_frac"][-1] == 1
        assert m["mass_frac"][0] == 0 and m["density_frac"][0] == m["pressure_frac"][0] == 1
        assert (m["mass_frac"][-1] == 1) == (m["n"] < 5), m["n"]
    assert models[6]["n"] == 3 and round(models[6]["sun_t_c_k"], -5) == 1.21e7
    with pytest.raises(ValueError):
        export.build_polytrope(n=1, flags=[], xi1=1, mass_constant=1, density_concentration=1,
                               sun=None, xi=[0, 1])


def profile_kwargs(**changes):
    arrays = {k: [0.0, 1.0] for k in export.PROFILE_ARRAYS} | {"convective": [False, True]}
    scalars = dict.fromkeys(export.PROFILE_SCALARS, 0.5)
    return {"mass_msun": 1.0, "feh": 0.0, "method": "test", "flags": ["test"], "x": 0.7,
            "y": 0.28, "z": 0.02, "scalars": scalars, "p_c_pa": 1e16, "energy_core_r_frac": 0.3,
            "pp_share": 0.99, "mist": scalars} | arrays | changes


def test_profile_document_matches_fixture_shape():
    meta = export.build_meta(dataset="test", models={"structure": "test"}, inputs={"stars": 1.0},
                             reference_keys=["Choi2016"])
    for mist in (dict.fromkeys(export.PROFILE_SCALARS, 0.4), None):
        profile = export.build_profile(**profile_kwargs(mist=mist))
        assert_shape(export.build_document(meta, profiles={"models": [profile]}), FIXTURE)
    assert profile["mist"] is None
    with pytest.raises(ValueError):
        export.build_profile(**profile_kwargs(nabla=[1.0]))


def test_planet_export_matches_fixture_shape(tmp_path, monkeypatch):
    """A real (small) planet cell through the export: population.json and a systems file."""
    from stellarforge import experiments
    cells = [experiments._planet_stats((1.0, feh, 60, 3, {})) for feh in (0.0, 0.3)]
    assert any(s["planets"] for c in cells for s in c["samples"])
    fake_runs = {"defaults": tuple({"hosts": {"gas giant": g}, "per_star": 1.0}
                                   for g in (0.1, 0.2, 0.3, 0.0))}
    monkeypatch.setattr(experiments, "PLANET_MASSES", (1.0,))
    monkeypatch.setattr(experiments, "PLANET_FEHS", (0.0, 0.3))
    monkeypatch.setattr(experiments, "planet_grid_cells", lambda: ((cells[0],), (cells[1],)))
    monkeypatch.setattr(experiments, "planet_sensitivity_cells", lambda: fake_runs)
    survey_cells = tuple(experiments._planet_stats((1.0, f, 60, 4, {"survey_only": True}))
                         for f in experiments.SURVEY_FEHS)
    assert "samples" not in survey_cells[0]
    monkeypatch.setattr(experiments, "planet_survey_cells", lambda: survey_cells)
    monkeypatch.setattr(experiments, "WEB_PLANETS", tmp_path)
    meta = export.build_meta(dataset="test", models={"planets": "test"}, inputs={"feh": 0.0},
                             reference_keys=["IdaLin2004a"], seed=3)
    population = json.loads(experiments.export_planets(meta).read_text())
    assert_shape(population, FIXTURE)
    labels = [c["label"] for c in population["population"]["conclusions"]]
    assert labels[:2] == ["prediction"] * 2
    assert labels[-7:] == ["observational constraint"] * 7       # the survey checks
    surveys_doc = experiments.planet_surveys({})
    assert len(surveys_doc["panels"][0]["rows"]) == 7
    systems = json.loads((tmp_path / "systems_001.json").read_text())
    assert_shape(systems, FIXTURE)
    assert len(systems["systems"]["systems"]) == 60
    with pytest.raises(ValueError):
        export.build_planet(planet_class="hot Jupiter", mass_mearth=1, radius_rearth=1, a_au=1,
                            a_form_au=1, f_env=0, ice_rich=False)


def test_schema_version_matches():
    assert FIXTURE["meta"]["schema_version"] == SCHEMA_VERSION
    assert exported_document()["meta"]["schema_version"] == SCHEMA_VERSION


def test_fixture_arrays_are_consistent():
    grid = FIXTURE["grid"]
    assert len(grid["tracks"]) == len(grid["mass_values_msun"])
    assert len(grid["files"]) == len(grid["feh_values"])
    for track in grid["tracks"]:
        assert len({len(track[name]) for name in export.TRACK_ARRAYS}) == 1
        assert all(len(p) == 3 for p in track["rgb"])
        assert track["provenance"] in export.PROVENANCE
        assert set(track["field_provenance"]) == set(export.TRACK_ARRAYS)


def test_fixture_reference_is_a_verified_one():
    known = json.loads((Path(export.__file__).parent / "references.json").read_text())
    assert all(ref in known for ref in FIXTURE["meta"]["references"])


def test_bad_tracks_are_rejected():
    good = {"mass_msun": 1, "feh": 0, "method": "m", "ending": "e", "age_yr": [1],
            "mass_now_msun": [1], "log_l_lsun": [0], "log_teff_k": [3.7], "log_r_rsun": [0],
            "phase": [0], "rgb": [[1, 1, 1]], "provenance": "derived", "flags": [],
            "phase_names": {0: "main sequence"}, "remnant": REMNANT}
    with pytest.raises(ValueError):
        export.build_track(**{**good, "age_yr": [1, 2]})
    with pytest.raises(ValueError):
        export.build_track(**{**good, "provenance": "guessed"})
    with pytest.raises(ValueError):
        export.build_track(**{**good, "remnant": {**REMNANT, "type": "quark star"}})
