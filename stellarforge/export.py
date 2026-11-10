"""Writes contract-shaped JSON with provenance. Every field is described in contract/README.md."""

import json
import multiprocessing
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from . import SCHEMA_VERSION, __version__, evolution
from .colour import temperature_to_rgb

PROVENANCE = ("published", "interpolated", "derived", "predicted")
TRACK_ARRAYS = ("age_yr", "mass_now_msun", "log_l_lsun", "log_teff_k", "log_r_rsun", "phase",
                "rgb")

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


def _round(values, digits: int) -> list[float]:
    return [float(f"{v:.{digits}g}") for v in values]


def build_track(*, mass_msun: float, feh: float, method: str, provenance: str, ending: str,
                flags: list[str], phase_names: dict[int, str], age_yr, mass_now_msun, log_l_lsun,
                log_teff_k, log_r_rsun, phase, rgb) -> dict:
    """One star's track. Arrays must be equally long; rgb is one [r, g, b] (sRGB, 0-1) per point.
    MIST values carry the track's provenance; the colour is always derived by Stellar-Forge."""
    if provenance not in PROVENANCE:
        raise ValueError(f"provenance must be one of {PROVENANCE}, got {provenance!r}")
    track = {
        "mass_msun": float(mass_msun),
        "feh": float(feh),
        "method": method,
        "provenance": provenance,
        "ending": ending,
        "flags": list(flags),
        "phase_names": {str(k): v for k, v in phase_names.items()},
        "field_provenance": {**{k: provenance for k in TRACK_ARRAYS if k != "rgb"},
                             "rgb": "derived"},
        # Ages are not rounded: some MIST points are microseconds apart (2e-6 yr at 2e8 yr).
        "age_yr": [float(x) for x in age_yr],
        "mass_now_msun": _round(mass_now_msun, 5),
        "log_l_lsun": _round(log_l_lsun, 5),
        "log_teff_k": _round(log_teff_k, 5),
        "log_r_rsun": _round(log_r_rsun, 5),
        "phase": [round(float(x)) for x in phase],
        "rgb": [_round(p, 4) for p in rgb],
    }
    lengths = {name: len(track[name]) for name in TRACK_ARRAYS}
    if len(set(lengths.values())) != 1 or any(len(p) != 3 for p in track["rgb"]):
        raise ValueError(f"track arrays must be equally long with 3-channel rgb, got {lengths}")
    return track


def build_grid(*, feh: float, feh_values, mass_values_msun, files: list[str],
               tracks: list[dict]) -> dict:
    """One [Fe/H] slice of the web grid; the sliders snap to feh_values and mass_values_msun."""
    if len(files) != len(feh_values):
        raise ValueError("one file per [Fe/H] value")
    return {
        "feh": float(feh),
        "feh_values": [float(x) for x in feh_values],
        "mass_values_msun": [float(x) for x in mass_values_msun],
        "files": list(files),
        "tracks": tracks,
    }


def build_document(meta: dict, grid: dict) -> dict:
    return {"meta": meta, "grid": grid}


def write_document(document: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written beside the target and renamed, so a killed export never leaves half a file
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(document, separators=(",", ":")) + "\n")
    tmp.replace(path)


# ---- The Phase 1 web grid -------------------------------------------------------------------

WEB_DATA = _HERE.parent / "web" / "public" / "data"
# 200 log-spaced masses, plus 1 M☉ exactly so the Sun can be picked.
WEB_MASSES_MSUN = np.union1d(np.geomspace(0.1, 300, 200), [1.0])
WEB_FEHS = np.round(np.arange(-4.0, 0.5 + 1e-9, 0.1), 1)
POINTS_PER_TRACK = 200
DATASET = "MIST v1.2, v/vcrit = 0.4, [α/Fe] = 0, Asplund et al. 2009 abundances"


def web_file(feh: float) -> str:
    return f"tracks_feh_{feh:+.1f}.json"


def web_track(mass_msun: float, feh: float) -> dict:
    """A track resampled to about POINTS_PER_TRACK points, keeping every primary EEP."""
    t = evolution.build_track(mass_msun, feh)
    v = t.values
    n = len(v["age_yr"])
    keep = np.union1d(np.round(np.linspace(0, n - 1, POINTS_PER_TRACK)).astype(int),
                      t.primary_eep_rows)
    return build_track(
        mass_msun=mass_msun, feh=feh, method=t.method, provenance=t.provenance, ending=t.ending,
        flags=t.flags, phase_names=t.phase_names, age_yr=v["age_yr"][keep], mass_now_msun=v["mass_msun"][keep],
        log_l_lsun=v["log_l_lsun"][keep], log_teff_k=v["log_teff_k"][keep],
        log_r_rsun=v["log_r_rsun"][keep], phase=v["phase"][keep],
        rgb=temperature_to_rgb(10 ** v["log_teff_k"][keep]),
    )


def web_document(feh: float) -> dict:
    meta = build_meta(
        dataset=DATASET,
        models={"track": "MIST v1.2 EEP tracks, bilinear EEP interpolation in log mass and [Fe/H]",
                "colour": "Helland blackbody fit, ported from Aion Forge"},
        inputs={"feh": float(feh)}, reference_keys=["Choi2016", "Dotter2016", "Paxton2011"],
    )
    grid = build_grid(
        feh=feh, feh_values=WEB_FEHS, mass_values_msun=_round(WEB_MASSES_MSUN, 5),
        files=[web_file(f) for f in WEB_FEHS],
        tracks=[web_track(m, feh) for m in _round(WEB_MASSES_MSUN, 5)],
    )
    return build_document(meta, grid)


def _write_web(feh: float) -> str:
    path = WEB_DATA / web_file(feh)
    write_document(web_document(feh), path)
    return f"{path.name}: {path.stat().st_size / 1e6:.1f} MB"


def main(argv: list[str]) -> None:
    if argv != ["web"]:
        raise SystemExit("Run: .venv/bin/python -m stellarforge.export web")
    with multiprocessing.Pool(4) as pool:  # the machine budget: at most 4 workers
        for line in pool.imap_unordered(_write_web, WEB_FEHS):
            print(line, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
