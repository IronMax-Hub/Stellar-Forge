"""Writes contract-shaped JSON with provenance. Every field is described in contract/README.md."""

import json
import multiprocessing
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from . import SCHEMA_VERSION, __version__, evolution, remnants
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


def git_commit_time() -> str:
    """The HEAD commit's time, UTC: a `created` that a rerun of the same code reproduces."""
    try:
        out = subprocess.run(["git", "-C", str(_HERE), "log", "-1", "--format=%ct"],
                             capture_output=True, text=True, check=True).stdout.strip()
        return datetime.fromtimestamp(int(out), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OSError, ValueError, subprocess.CalledProcessError):
        return "unknown"


def build_meta(*, dataset: str, models: dict[str, str], inputs: dict[str, float],
               reference_keys: list[str], seed: int | None = None,
               created: str | None = None) -> dict:
    """The provenance block every export carries. Unknown reference keys raise KeyError.
    `created` defaults to now; reproducible runs pass git_commit_time() instead."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": "stellarforge", "version": __version__, "git_commit": _git_commit()},
        "dataset": dataset,
        "models": dict(models),
        "inputs": dict(inputs),
        "seed": seed,
        "created": created or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "references": [_REFERENCES[k] for k in reference_keys],
    }


def _round(values, digits: int) -> list[float]:
    return [float(f"{v:.{digits}g}") for v in values]


def build_track(*, mass_msun: float, feh: float, method: str, provenance: str, ending: str,
                flags: list[str], phase_names: dict[int, str], age_yr, mass_now_msun, log_l_lsun,
                log_teff_k, log_r_rsun, phase, rgb, remnant: dict) -> dict:
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
        "remnant": build_remnant(**remnant),
    }
    lengths = {name: len(track[name]) for name in TRACK_ARRAYS}
    if len(set(lengths.values())) != 1 or any(len(p) != 3 for p in track["rgb"]):
        raise ValueError(f"track arrays must be equally long with 3-channel rgb, got {lengths}")
    return track


REMNANT_TYPES = ("white dwarf", "neutron star", "black hole", "none", "not yet", "not predicted")
COOLING_ARRAYS = ("cooling_age_yr", "log_l_lsun", "log_teff_k", "radius_km")


def _maybe(x, digits=4):
    return None if x is None else float(f"{x:.{digits}g}")


def build_remnant(*, type: str, mass_msun, radius_km, provenance: str, prescription: str,
                  how: str, alternative: dict, final_mass_msun, he_core_mass_msun,
                  co_core_mass_msun, flags: list[str], cooling: dict | None) -> dict:
    """A star's remnant (stellarforge.remnants.Remnant.as_dict()). mass, radius and cooling are
    null when there is no remnant; the alternative is the other prescription's answer."""
    if type not in REMNANT_TYPES or alternative["type"] not in REMNANT_TYPES:
        raise ValueError(f"remnant type must be one of {REMNANT_TYPES}")
    if provenance not in PROVENANCE:
        raise ValueError(f"provenance must be one of {PROVENANCE}, got {provenance!r}")
    if cooling is not None and len({len(cooling[k]) for k in COOLING_ARRAYS}) != 1:
        raise ValueError("cooling arrays must be equally long")
    return {
        "type": type, "mass_msun": _maybe(mass_msun), "radius_km": _maybe(radius_km),
        "provenance": provenance, "prescription": prescription, "how": how,
        "alternative": {"prescription": alternative["prescription"], "type": alternative["type"],
                        "mass_msun": _maybe(alternative["mass_msun"])},
        # NaN marks a core mass MIST does not give; JSON has no NaN, so it is exported as null
        **{k: _maybe(None if np.isnan(v) else v) for k, v in (
            ("final_mass_msun", final_mass_msun), ("he_core_mass_msun", he_core_mass_msun),
            ("co_core_mass_msun", co_core_mass_msun))},
        "flags": list(flags),
        "cooling": None if cooling is None else {k: _round(cooling[k], 5) for k in COOLING_ARRAYS},
    }


PANEL_KINDS = ("heatmap", "curves", "table")


def build_row(*, label: str, values, labels=None, provenance=None, y: float | None = None) -> dict:
    """One heatmap row, curve or table row. Each cell is a number (`values`), a word (`labels`,
    used where not null) or empty; `provenance` says where each cell came from."""
    n = len(values)
    labels = [None] * n if labels is None else list(labels)
    provenance = [None] * n if provenance is None else list(provenance)
    if not len(labels) == len(provenance) == n:
        raise ValueError(f"row {label!r}: values, labels and provenance differ in length")
    if any(p is not None and p not in PROVENANCE for p in provenance):
        raise ValueError(f"row {label!r}: provenance must be one of {PROVENANCE}")
    return {"label": label, "y": None if y is None else float(y),
            "values": [None if v is None or np.isnan(v) else float(f"{v:.5g}") for v in values],
            "labels": labels, "provenance": provenance}


def build_panel(*, title: str, kind: str, rows: list[dict], x_label: str = "", y_label: str = "",
                value_label: str = "", log_x: bool = False, log_values: bool = False,
                x_values=(), columns=()) -> dict:
    """A heatmap (rows of cells over x_values), curves (one row per curve over x_values) or a
    table (rows of cells under columns)."""
    if kind not in PANEL_KINDS:
        raise ValueError(f"panel kind must be one of {PANEL_KINDS}")
    width = len(columns) if kind == "table" else len(x_values)
    if any(len(r["values"]) != width for r in rows):
        raise ValueError(f"panel {title!r}: every row needs {width} cells")
    return {"title": title, "kind": kind, "x_label": x_label, "y_label": y_label,
            "value_label": value_label, "log_x": log_x, "log_values": log_values,
            "x_values": [float(f"{x:.5g}") for x in x_values], "columns": list(columns),
            "rows": rows}


def build_experiment(*, name: str, title: str, summary: str, panels: list[dict]) -> dict:
    return {"name": name, "title": title, "summary": summary, "panels": panels}


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


def build_document(meta: dict, grid: dict | None = None, experiment: dict | None = None) -> dict:
    """meta plus the blocks this document carries (a grid, an experiment or both)."""
    blocks = {"grid": grid, "experiment": experiment}
    return {"meta": meta, **{k: v for k, v in blocks.items() if v is not None}}


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
        flags=t.flags, phase_names=t.phase_names, age_yr=v["age_yr"][keep],
        mass_now_msun=v["mass_msun"][keep],
        log_l_lsun=v["log_l_lsun"][keep], log_teff_k=v["log_teff_k"][keep],
        log_r_rsun=v["log_r_rsun"][keep], phase=v["phase"][keep],
        rgb=temperature_to_rgb(10 ** v["log_teff_k"][keep]),
        remnant=remnants.remnant(t, mass_msun).as_dict(),
    )


def web_document(feh: float) -> dict:
    meta = build_meta(
        dataset=DATASET,
        models={"track": "MIST v1.2 EEP tracks, bilinear EEP interpolation in log mass and [Fe/H]",
                "colour": "Helland blackbody fit, ported from Aion Forge",
                "remnant": "fryer2012-delayed (alternative fryer2012-rapid); "
                           "belczynski2016-m10 pair instability",
                "white_dwarf_mass": "MIST final mass (alternative cummings2018-mist-ifmr)",
                "white_dwarf_cooling": "bedard2020-thick-h"},
        inputs={"feh": float(feh)},
        reference_keys=["Choi2016", "Dotter2016", "Paxton2011", "Fryer2012", "Belczynski2016",
                        "HegerWoosley2002", "Cummings2018", "Bedard2020", "Poelarends2008",
                        "OzelFreire2016", "Prsa2016", "Sana2012"],
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
