"""Writes contract-shaped JSON with provenance. Every field is described in contract/README.md."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from . import SCHEMA_VERSION, __version__

PROVENANCE = ("published", "interpolated", "derived", "predicted")
TRACK_ARRAYS = ("age_yr", "log_l_lsun", "log_teff_k", "log_r_rsun", "rgb")

_HERE = Path(__file__).parent
_REFERENCES = {r["key"]: r for r in json.loads((_HERE / "references.json").read_text())}


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(_HERE), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_meta(*, dataset: str, models: dict[str, str], inputs: dict[str, float],
               reference_keys: list[str], seed: int | None = None) -> dict:
    """The provenance block every export carries. Unknown reference keys raise KeyError."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": "stellarforge", "version": __version__, "git_commit": _git_commit()},
        "dataset": dataset,
        "models": dict(models),
        "inputs": dict(inputs),
        "seed": seed,
        "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "references": [_REFERENCES[k] for k in reference_keys],
    }


def build_track(*, age_yr, log_l_lsun, log_teff_k, log_r_rsun, rgb,
                provenance: str, flags: list[str]) -> dict:
    """One star's track. Arrays must be equally long; rgb is one [r, g, b] (sRGB, 0-1) per point."""
    if provenance not in PROVENANCE:
        raise ValueError(f"provenance must be one of {PROVENANCE}, got {provenance!r}")
    track = {
        "provenance": provenance,
        "flags": list(flags),
        "age_yr": [float(x) for x in age_yr],
        "log_l_lsun": [float(x) for x in log_l_lsun],
        "log_teff_k": [float(x) for x in log_teff_k],
        "log_r_rsun": [float(x) for x in log_r_rsun],
        "rgb": [[float(c) for c in p] for p in rgb],
    }
    lengths = {name: len(track[name]) for name in TRACK_ARRAYS}
    if len(set(lengths.values())) != 1 or any(len(p) != 3 for p in track["rgb"]):
        raise ValueError(f"track arrays must be equally long with 3-channel rgb, got {lengths}")
    return track


def build_document(meta: dict, track: dict) -> dict:
    return {"meta": meta, "track": track}


def write_document(document: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1) + "\n")
