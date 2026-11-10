"""Contract test: export.py must produce the shape of contract/fixture.json. Shape only, never values."""

import json
from pathlib import Path

import pytest

from stellarforge import SCHEMA_VERSION, export

FIXTURE = json.loads((Path(__file__).parent.parent / "contract" / "fixture.json").read_text())


def shape(value):
    """Keys and value types, recursively; a list is described by its first element."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return type(value).__name__


def exported_document():
    meta = export.build_meta(
        dataset="test", models={"colour": "test"}, inputs={"mass_msun": 2.0, "feh": -0.5},
        reference_keys=["Choi2016"],
    )
    track = export.build_track(
        age_yr=[1, 2], log_l_lsun=[0, 1], log_teff_k=[3.7, 3.8], log_r_rsun=[0, 0.1],
        rgb=[[1, 1, 1], [1, 0.9, 0.8]], provenance="derived", flags=["test"],
    )
    return export.build_document(meta, track)


def test_export_matches_fixture_shape():
    assert shape(exported_document()) == shape(FIXTURE)


def test_schema_version_matches():
    assert FIXTURE["meta"]["schema_version"] == SCHEMA_VERSION
    assert exported_document()["meta"]["schema_version"] == SCHEMA_VERSION


def test_fixture_arrays_are_consistent():
    track = FIXTURE["track"]
    assert len({len(track[name]) for name in export.TRACK_ARRAYS}) == 1
    assert all(len(p) == 3 for p in track["rgb"])
    assert track["provenance"] in export.PROVENANCE


def test_fixture_reference_is_a_verified_one():
    known = json.loads((Path(export.__file__).parent / "references.json").read_text())
    assert all(ref in known for ref in FIXTURE["meta"]["references"])


def test_bad_tracks_are_rejected():
    good = {"age_yr": [1], "log_l_lsun": [0], "log_teff_k": [3.7], "log_r_rsun": [0], "rgb": [[1, 1, 1]],
                "provenance": "derived", "flags": []}
    with pytest.raises(ValueError):
        export.build_track(**{**good, "age_yr": [1, 2]})
    with pytest.raises(ValueError):
        export.build_track(**{**good, "provenance": "guessed"})
