"""Which files in web/public/data were made by older code (Phase 7, data freshness).

Run: .venv/bin/python -m scripts.data_status     (or `make data-status`)

Lists every data file whose schema version is not the current one, or whose generator commit is
older than the last commit that changed stellarforge/ (or carried uncommitted changes), with the
make target that rebuilds it. Also writes web/public/data/index.json (contract/README.md, "index"),
which the app reads at start-up to name stale files before a view opens one.
Always exits 0: the data is gitignored, so stale or missing data is a warning, not a failure.
"""

import json
import re
import subprocess
from functools import cache
from pathlib import Path

from stellarforge import SCHEMA_VERSION
from stellarforge.export import WEB_DATA

ROOT = Path(__file__).parent.parent
INDEX = "index.json"
# Both writers put `meta` first, so a file's head holds these two fields; a 140 MB grid is not parsed
HEAD_BYTES = 2048
SCHEMA = re.compile(r'"schema_version":\s*(\d+)')
COMMIT = re.compile(r'"git_commit":\s*"([^"]*)"')


def target(file: str) -> str:
    """The make target that writes this file (see the Makefile)."""
    if file.startswith(("planets/", "experiments/planet-")):
        return "planets"
    if file == "experiments/zams-extension.json":
        return "extension"
    return "experiments" if file.startswith("experiments/") else "export"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=False, capture_output=True,
                          text=True)


@cache
def code_commit() -> str:
    """The last commit that changed the physics code."""
    return _git("log", "-1", "--format=%h", "--", "stellarforge").stdout.strip()


@cache
def made_by_current_code(commit: str) -> bool:
    """True when the file's commit holds the current physics code, with nothing uncommitted."""
    if commit.endswith("+changes") or not code_commit():
        return False
    return _git("merge-base", "--is-ancestor", code_commit(), commit).returncode == 0


def scan(data: Path = WEB_DATA) -> list[dict]:
    """One entry per data file: file, schema_version (None if unreadable), target, and stale
    (why it is out of date, or None)."""
    entries = []
    for path in sorted(data.rglob("*.json")):
        file = path.relative_to(data).as_posix()
        if file == INDEX:
            continue
        with path.open("rb") as f:
            head = f.read(HEAD_BYTES).decode("utf-8", "replace")
        schema, commit = SCHEMA.search(head), COMMIT.search(head)
        version = int(schema.group(1)) if schema else None
        if version is None or commit is None:
            stale = "no meta block at the start of the file"
        elif version != SCHEMA_VERSION:
            stale = f"schema {version}, current {SCHEMA_VERSION}"
        elif not made_by_current_code(commit.group(1)):
            stale = f"made by {commit.group(1)}, physics code is at {code_commit() or 'unknown'}"
        else:
            stale = None
        entries.append({"file": file, "schema_version": version, "target": target(file),
                        "stale": stale})
    return entries


def write_index(entries: list[dict], data: Path = WEB_DATA) -> None:
    files = [{k: e[k] for k in ("file", "schema_version", "target")} for e in entries]
    (data / INDEX).write_text(json.dumps({"schema_version": SCHEMA_VERSION, "files": files},
                                         separators=(",", ":")) + "\n")


def main() -> None:
    if not WEB_DATA.is_dir():
        print("data-status: no web/public/data; run `make all-data`")
        return
    entries = scan()
    write_index(entries)
    stale = [e for e in entries if e["stale"]]
    if not stale:
        print(f"data-status: all {len(entries)} data files are current")
        return
    for name in sorted({e["target"] for e in stale}):
        group = [e for e in stale if e["target"] == name]
        print(f"data-status: {len(group)} stale, rebuild with `make {name}`:")
        for e in group:
            print(f"  {e['file']}: {e['stale']}")
    print(f"data-status: WARNING, {len(stale)} of {len(entries)} data files are stale")


if __name__ == "__main__":
    main()
