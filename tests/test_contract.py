"""Contract test: export.py must produce the shape of contract/fixture.json. Shape only, never values."""

import json
from pathlib import Path

import pytest

from stellarforge import SCHEMA_VERSION, evolution, export

FIXTURE = json.loads((Path(__file__).parent.parent / "contract" / "fixture.json").read_text())


# Objects whose keys vary between documents (contract/README.md: "object of ..."); every value must
# match the fixture's value kind.
MAPS = {"inputs", "models", "phase_names"}
# Remnant fields that are null when there is no remnant or MIST gives no value.
NULLABLE = {"mass_msun", "radius_km", "cooling", "final_mass_msun", "he_core_mass_msun",
            "co_core_mass_msun"}


def kind(value):
    return "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else \
        type(value).__name__


def assert_shape(actual, expected, path="document", key=None):
    """Same keys and value kinds as the fixture, recursively; every list item is checked against
    the fixture's first item."""
    if key in NULLABLE and (actual is None or expected is None):
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
        for i, item in enumerate(actual if expected else []):
            assert_shape(item, expected[0], f"{path}[{i}]")
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
