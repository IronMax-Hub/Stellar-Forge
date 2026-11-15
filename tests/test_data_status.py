"""scripts/data_status.py: stale files are found and the index has the shape of
contract/index.fixture.json (its web twin is in web/src/__tests__/contract.test.ts)."""

import json
from pathlib import Path

from scripts import data_status
from stellarforge import SCHEMA_VERSION

FIXTURE = json.loads((Path(__file__).parent.parent / "contract" / "index.fixture.json").read_text())


def _write(path: Path, schema: int, commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": {"schema_version": schema,
                                         "generator": {"git_commit": commit}}}))


def test_scan_finds_stale_files_and_writes_the_index(tmp_path):
    current = data_status.code_commit()
    _write(tmp_path / "tracks_feh_+0.0.json", SCHEMA_VERSION, current)
    _write(tmp_path / "planets" / "systems_000.json", SCHEMA_VERSION - 2, current)
    _write(tmp_path / "experiments" / "planet-grid.json", SCHEMA_VERSION, current + "+changes")
    _write(tmp_path / "experiments" / "zams-extension.json", SCHEMA_VERSION, "0000000")
    (tmp_path / "experiments" / "broken.json").write_text("{}")

    entries = {e["file"]: e for e in data_status.scan(tmp_path)}
    assert entries["tracks_feh_+0.0.json"]["stale"] is None
    assert "schema" in entries["planets/systems_000.json"]["stale"]
    assert "+changes" in entries["experiments/planet-grid.json"]["stale"]
    assert entries["experiments/zams-extension.json"]["stale"]
    assert entries["experiments/broken.json"]["schema_version"] is None
    assert [entries[f]["target"] for f in sorted(entries)] == [
        "experiments", "planets", "extension", "planets", "export"]

    data_status.write_index(list(entries.values()), tmp_path)
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["schema_version"] == FIXTURE["schema_version"] == SCHEMA_VERSION
    assert all(f.keys() == FIXTURE["files"][0].keys() for f in index["files"])
    # The index never lists itself
    assert "index.json" not in {e["file"] for e in data_status.scan(tmp_path)}
