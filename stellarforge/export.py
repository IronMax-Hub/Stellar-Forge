"""Writes contract-shaped JSON with provenance. Every field is described in contract/README.md."""

import json
import multiprocessing
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from . import SCHEMA_VERSION, __version__, evolution, remnants, structure
from .colour import temperature_to_rgb
from .planets.classify import CLASSES

PROVENANCE = ("published", "interpolated", "substituted", "derived", "predicted")
TRACK_ARRAYS = ("age_yr", "mass_now_msun", "log_l_lsun", "log_teff_k", "log_r_rsun", "phase",
                "rgb")

_HERE = Path(__file__).parent
_REFERENCES = {r["key"]: r for r in json.loads((_HERE / "references.json").read_text())}


def code_changed() -> bool:
    """True when stellarforge/ differs from the HEAD commit (edited or new files)."""
    try:
        return subprocess.run(["git", "-C", str(_HERE), "status", "--porcelain", "--", "."],
                              capture_output=True, text=True, check=True).stdout.strip() != ""
    except (OSError, subprocess.CalledProcessError):
        return True


def _git_commit() -> str:
    """HEAD's short hash, with "+changes" when the physics code differs from it: then that commit
    alone did not make the result."""
    try:
        head = subprocess.run(
            ["git", "-C", str(_HERE), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return head + ("+changes" if code_changed() else "")


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


# ---- Phase 5: planet populations ------------------------------------------------------------

PLANET_CLASSES = CLASSES
CALIBRATION = ("observational constraint", "prediction", "parameter-sensitive", "extrapolation")
CORES = ("ice-rich", "rock-dominated")


def _check(value, allowed, what):
    if value not in allowed:
        raise ValueError(f"{what} must be one of {allowed}, got {value!r}")
    return value


def build_population_cell(*, m_star_msun: float, feh: float, n_systems: int, seed: int,
                          calibration: str, host_share: dict, planets_per_star: float,
                          systems_with_count: list[int], a_ice_au: float,
                          systems_file: str, timeline_file: str, flags: list[str]) -> dict:
    """One grid cell's statistics. host_share: share of systems with at least one planet of each
    class; systems_with_count[k]: systems with exactly k planets; flags: validity warnings, such as
    the survey checks the model fails."""
    if set(host_share) != set(PLANET_CLASSES):
        raise ValueError(f"host_share needs one share per class {PLANET_CLASSES}")
    if sum(systems_with_count) != n_systems:
        raise ValueError("systems_with_count must add up to n_systems")
    return {"m_star_msun": float(m_star_msun), "feh": float(feh), "n_systems": int(n_systems),
            "seed": int(seed), "calibration": _check(calibration, CALIBRATION, "calibration"),
            "provenance": "predicted",
            "host_share": {k: float(f"{host_share[k]:.5g}") for k in PLANET_CLASSES},
            "planets_per_star": float(f"{planets_per_star:.5g}"),
            "systems_with_count": [int(c) for c in systems_with_count],
            "a_ice_au": float(f"{a_ice_au:.5g}"), "systems_file": systems_file,
            "timeline_file": timeline_file,
            "flags": [str(f) for f in flags]}


def build_population(*, star_masses_msun, feh_values, calibration_mass_msun, calibration_feh,
                     cells: list[dict], conclusions: list[dict]) -> dict:
    """The planet grid: one cell per star mass and [Fe/H] ([Fe/H]-major order); the view's
    selectors snap to star_masses_msun and feh_values. conclusions: {statement, label}."""
    if len(cells) != len(star_masses_msun) * len(feh_values):
        raise ValueError("one cell per star mass and [Fe/H]")
    for c in conclusions:
        _check(c["label"], CALIBRATION, "conclusion label")
    return {"star_masses_msun": [float(m) for m in star_masses_msun],
            "feh_values": [float(f) for f in feh_values], "classes": list(PLANET_CLASSES),
            "calibration_mass_msun": [float(x) for x in calibration_mass_msun],
            "calibration_feh": [float(x) for x in calibration_feh], "cells": cells,
            "conclusions": [{"statement": c["statement"], "label": c["label"]}
                            for c in conclusions]}


def build_planet(*, planet_class: str, mass_mearth: float, radius_rearth: float, a_au: float,
                 a_form_au: float, f_env: float, ice_rich: bool) -> dict:
    """One planet when the gas disk is gone. Its radius is derived (Chen & Kipping 2017); the rest
    is the model's prediction."""
    return {"class": _check(planet_class, PLANET_CLASSES, "class"),
            "mass_mearth": float(f"{mass_mearth:.5g}"),
            "radius_rearth": float(f"{radius_rearth:.4g}"), "a_au": float(f"{a_au:.5g}"),
            "a_form_au": float(f"{a_form_au:.5g}"), "f_env": float(f"{f_env:.4g}"),
            "core": CORES[0] if ice_rich else CORES[1], "provenance": "predicted",
            "radius_provenance": "derived"}


def build_systems(*, m_star_msun: float, feh: float, seed: int, calibration: str, a_ice_au: float,
                  systems: list[dict]) -> dict:
    """Sample systems of one cell; each is {index, f_g0, f_d0, tau_disk_yr, planets}, planets
    from the inside out."""
    return {"m_star_msun": float(m_star_msun), "feh": float(feh), "seed": int(seed),
            "calibration": _check(calibration, CALIBRATION, "calibration"),
            "a_ice_au": float(f"{a_ice_au:.5g}"),
            "systems": [{"index": int(s["index"]), "f_g0": float(f"{s['f_g0']:.4g}"),
                         "f_d0": float(f"{s['f_d0']:.4g}"),
                         "tau_disk_yr": float(f"{s['tau_disk_yr']:.4g}"),
                         "planets": sorted(s["planets"], key=lambda p: p["a_au"])}
                        for s in systems]}


def _sig(values, digits: int = 4) -> list:
    """Numbers to `digits` significant figures; NaN becomes null."""
    return [None if not np.isfinite(v) else float(f"{v:.{digits}g}") for v in values]


def build_timeline_star(*, track, hist, samples) -> dict:
    """The star at the exported ages (planets/coevolution.py StarHistory at `samples`); the
    habitable-zone edges are null where Kopparapu et al. 2013 do not apply."""
    return {"provenance": track.provenance, "method": track.method, "ending": track.ending,
            "flags": [*track.flags, *hist.flags], "age_yr": _sig(hist.age_yr[samples], 6),
            "mass_msun": _sig(hist.mass_msun[samples]), "radius_au": _sig(hist.radius_au[samples]),
            "l_lsun": _sig(hist.l_lsun[samples]), "teff_k": _sig(hist.teff_k[samples]),
            "hz_inner_au": _sig(hist.hz_inner_au[samples]),
            "hz_outer_au": _sig(hist.hz_outer_au[samples]),
            "phase": [hist.phase_name(i) for i in samples],
            "rgb": [_round(c, 4) for c in temperature_to_rgb(hist.teff_k[samples])]}


def _orbit_knots(a_au) -> tuple[list[int], list[float]]:
    """The exported orbit as (sample index, a) knots: inside a run of equal values only its ends
    are kept, so linear drawing between knots reproduces the series; NaN (gone) ends it."""
    a = np.asarray(a_au, float)
    a = a[:np.flatnonzero(np.isfinite(a))[-1] + 1]
    flat = np.isclose(a[1:-1], a[:-2], rtol=1e-4) & np.isclose(a[1:-1], a[2:], rtol=1e-4)
    keep = np.flatnonzero(~np.concatenate([[False], flat, [False]]))
    return [int(i) for i in keep], _sig(a[keep], 5)


def build_timeline_planet(*, result: dict, i: int, name: str | None, planet_class: str,
                          mass_mearth: float) -> dict:
    """Planet i of a coevolution.evolve_planets result."""
    from .planets.coevolution import EVENT_KINDS, FATES
    sample, a = _orbit_knots(result["a_au"][i])
    events = result["events"][i]
    for e in events:
        _check(e["kind"], EVENT_KINDS, "event kind")
    return {"name": name, "class_at_formation": _check(planet_class, PLANET_CLASSES, "class"),
            "class_final": _check(str(result["final_class"][i]), PLANET_CLASSES, "class"),
            "mass_mearth": float(f"{mass_mearth:.5g}"),
            "final_mass_mearth": float(f"{result['final_mass_mearth'][i]:.5g}"),
            "final_f_env": float(f"{result['final_f_env'][i]:.4g}"),
            "orbit_sample": sample, "orbit_a_au": a,
            "fate": _check(str(result["fate"][i]), FATES, "fate"),
            "closest_approach_rstar": float(f"{result['closest_approach_rstar'][i]:.4g}"),
            "deciding_phase": str(result["deciding_phase"][i]),
            "xuv_dose_earth": float(f"{result['xuv_dose_earth'][i]:.4g}"),
            "shoreline": "lost" if result["shoreline_crossed"][i] else "kept",
            "air_retained": float(f"{result['air_retained'][i]:.4g}"),
            "events": events, "flags": list(result["flags"][i]), "provenance": "predicted"}


def build_timeline(*, name: str, m_star_msun: float, feh: float, systems_file: str | None,
                   star: dict, systems: list[dict]) -> dict:
    """Planets through their star's life: the star at the exported ages and, per system
    ({index, planets}), each planet's orbit, events and fate. Planets keep the order of
    systems_file (the Phase 5 sample systems they continue), or are named (the Solar System)."""
    n = len(star["age_yr"])
    if any(len(v) != n for k, v in star.items() if isinstance(v, list) and k != "flags"):
        raise ValueError("every star series needs one value per exported age")
    return {"name": name, "m_star_msun": float(m_star_msun), "feh": float(feh),
            "systems_file": systems_file, "star": star, "systems": systems}


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


POLYTROPE_ARRAYS = ("radius_frac", "xi", "theta", "mass_frac", "density_frac", "pressure_frac")


def build_polytrope(*, n: float, flags: list[str], xi1, mass_constant: float,
                    density_concentration, sun: dict | None, **arrays) -> dict:
    """One Lane-Emden polytrope; xi1, the concentration and the Sun scaling are null for n = 5."""
    if set(arrays) != set(POLYTROPE_ARRAYS) or len({len(v) for v in arrays.values()}) != 1:
        raise ValueError(f"a polytrope needs equally long arrays {POLYTROPE_ARRAYS}")
    finite = (lambda x: None if x is None or not np.isfinite(x) else float(f"{x:.6g}"))
    sun = sun or {}
    return {
        "n": float(n), "provenance": "derived", "flags": list(flags),
        "xi1": finite(xi1), "mass_constant": finite(mass_constant),
        "density_concentration": finite(density_concentration),
        **{k: finite(sun.get(k)) for k in ("sun_rho_c_kg_m3", "sun_p_c_pa", "sun_t_c_k")},
        **{k: _round(arrays[k], 6) for k in POLYTROPE_ARRAYS},
    }


PROFILE_ARRAYS = ("r_frac", "m_frac", "l_frac", "t_frac", "rho_frac", "p_frac", "eps_pp_w_kg",
                  "eps_cno_w_kg", "kappa_m2_kg", "nabla", "nabla_ad", "nabla_rad", "convective")
PROFILE_SCALARS = ("log_l_lsun", "log_r_rsun", "log_teff_k", "log_t_c_k", "log_rho_c_kg_m3")


def build_profile(*, mass_msun: float, feh: float, method: str, flags: list[str], x: float,
                  y: float, z: float, scalars: dict, p_c_pa: float, energy_core_r_frac: float,
                  pp_share: float, mist: dict | None, **arrays) -> dict:
    """One star's zero-age structure from the centre to the surface. `scalars` and `mist` hold
    PROFILE_SCALARS; mist is MIST's zero-age star, or None where there is none to compare."""
    if set(arrays) != set(PROFILE_ARRAYS) or len({len(v) for v in arrays.values()}) != 1:
        raise ValueError(f"a profile needs equally long arrays {PROFILE_ARRAYS}")
    if set(scalars) != set(PROFILE_SCALARS) or (mist is not None and set(mist) != set(scalars)):
        raise ValueError(f"profile scalars must be {PROFILE_SCALARS}")
    return {
        "mass_msun": float(mass_msun), "feh": float(feh), "provenance": "derived",
        "method": method, "flags": list(flags), "x": float(f"{x:.6g}"), "y": float(f"{y:.6g}"), "z": float(f"{z:.6g}"),
        **{k: float(f"{v:.6g}") for k, v in scalars.items()},
        "p_c_pa": float(f"{p_c_pa:.6g}"), "energy_core_r_frac": float(f"{energy_core_r_frac:.4g}"),
        "pp_share": float(f"{pp_share:.4g}"),
        "mist": None if mist is None else {
            "provenance": "published", **{k: float(f"{v:.6g}") for k, v in mist.items()},
            **{f"delta_{k}": float(f"{scalars[k] - v:.4g}") for k, v in mist.items()}},
        **{k: [bool(b) for b in v] if k == "convective" else _round(v, 6)
           for k, v in arrays.items()},
    }


def build_document(meta: dict, grid: dict | None = None, experiment: dict | None = None,
                   polytropes: dict | None = None, profiles: dict | None = None,
                   population: dict | None = None, systems: dict | None = None,
                   timeline: dict | None = None) -> dict:
    """meta plus the blocks this document carries (a grid, an experiment, polytropes, profiles,
    a planet population, one cell's sample systems or their timelines)."""
    blocks = {"grid": grid, "experiment": experiment, "polytropes": polytropes,
              "profiles": profiles, "population": population, "systems": systems,
              "timeline": timeline}
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


# ---- Phase 4 polytropes ---------------------------------------------------------------------

POLYTROPE_NS = np.arange(0, 5.0 + 1e-9, 0.5)
SUN_X, SUN_Y, SUN_Z = 0.70, 0.28, 0.02   # the build plan's Eddington check: mu = 0.617


def polytrope_record(n: float) -> dict:
    poly = structure.lane_emden(n, points=200)
    surface = np.isfinite(poly.xi1)
    mu = structure.mean_molecular_weight(SUN_X, SUN_Y, SUN_Z)
    sun = structure.polytrope_star(poly, 1.0, 1.0, mu) if surface else None
    return build_polytrope(
        n=n, flags=[] if surface else ["no_surface_profile_cut_at_xi_50"],
        xi1=poly.xi1, mass_constant=poly.mass_constant,
        density_concentration=poly.concentration,
        sun=sun and {"sun_rho_c_kg_m3": sun.rho_c_kg_m3, "sun_p_c_pa": sun.p_c_pa,
                     "sun_t_c_k": sun.t_c_k},
        radius_frac=poly.xi / poly.xi[-1], xi=poly.xi, theta=poly.theta,
        # m(xi)/M = xi^2 |theta'| / (xi_1^2 |theta'(xi_1)|); for n = 5 the limit sqrt(3)
        mass_frac=np.minimum(-poly.xi**2 * poly.dtheta / poly.mass_constant, 1.0),
        density_frac=poly.theta**n, pressure_frac=poly.theta ** (n + 1),
    )


def polytrope_document() -> dict:
    meta = build_meta(
        dataset="none: solutions of the Lane-Emden equation",
        models={"structure": "Lane-Emden polytropes, SciPy DOP853 (stellarforge.structure)",
                "sun_scaling": "1 M☉, 1 R☉, ideal gas, mu = 0.617 (X 0.70, Y 0.28, Z 0.02)"},
        inputs={"n_min": 0.0, "n_max": 5.0, "n_step": 0.5},
        reference_keys=["Chandrasekhar1939", "Kippenhahn2012", "Prsa2016"],
        created=git_commit_time(),
    )
    return build_document(meta, polytropes={
        "n_values": [float(n) for n in POLYTROPE_NS],
        "models": [polytrope_record(n) for n in POLYTROPE_NS]})


# ---- Phase 4 zero-age main-sequence profiles ---------------------------------------------------

ZAMS_STARS = ((1.0, 0.0),)    # (M☉, [Fe/H]); the gate star. The extension adds more.
ZAMS_FLAGS = ["kww_formulae_not_yet_source_checked", "pressure_ionisation_blended_log_t_6_to_6.5",
              "mlt_bohm_vitense_not_henyey", "grey_eddington_photosphere"]


def zams_profile(mass_msun: float, feh: float) -> dict:
    mist = structure.mist_zams(mass_msun, feh)
    model = structure.solve_zams(mass_msun, feh, composition=mist.composition)
    q = structure.profile_quantities(model)
    comp = model.composition
    lum, m, r = model.l_w, model.m_kg, model.r_m
    eps_pp_total = np.trapezoid(q["eps_pp_w_kg"], m)
    scalars = {"log_l_lsun": np.log10(model.luminosity_lsun),
               "log_r_rsun": np.log10(model.radius_rsun), "log_teff_k": np.log10(model.teff_k),
               "log_t_c_k": np.log10(model.t_c_k), "log_rho_c_kg_m3": np.log10(model.rho_c_kg_m3)}
    mist_scalars = {k: getattr(mist, k) for k in PROFILE_SCALARS}
    return build_profile(
        mass_msun=mass_msun, feh=feh, flags=ZAMS_FLAGS, x=comp.x, y=comp.y, z=comp.z,
        method="zero-age model fitted at half the mass (milestone 5), X Y Z from the MIST archive",
        scalars=scalars, p_c_pa=model.p_c_pa,
        energy_core_r_frac=r[np.searchsorted(lum / lum[-1], 0.99)] / r[-1],
        pp_share=eps_pp_total / (eps_pp_total + np.trapezoid(q["eps_cno_w_kg"], m)),
        mist=mist_scalars,
        r_frac=r / r[-1], m_frac=m / m[-1], l_frac=lum / lum[-1], t_frac=model.t_k / model.t_c_k,
        rho_frac=q["rho_kg_m3"] / model.rho_c_kg_m3, p_frac=model.p_pa / model.p_c_pa,
        **{k: q[k] for k in ("eps_pp_w_kg", "eps_cno_w_kg", "kappa_m2_kg", "nabla", "nabla_ad",
                             "nabla_rad", "convective")})


def zams_document() -> dict:
    meta = build_meta(
        dataset="MIST v1.2 zero-age stars for comparison; OPAL and Ferguson et al. 2005 opacity "
                "tables for the Asplund et al. 2009 mixture, from MESA",
        models={"structure": "four structure equations fitted at half the mass (stellarforge."
                             "structure, milestone 5)",
                "equation_of_state": "ideal gas plus radiation, Saha ionisation of H and He",
                "convection": "Schwarzschild criterion, mixing length alpha = 1.82",
                "energy": "analytic pp chain and CNO cycle (Kippenhahn, Weigert & Weiss 2012)",
                "photosphere": "grey Eddington, T = Teff where P = (2/3) g / kappa"},
        inputs={"stars": float(len(ZAMS_STARS))},
        reference_keys=["Choi2016", "Kippenhahn2012", "IglesiasRogers1996", "Asplund2009",
                        "Prsa2016"],
        created=git_commit_time(),
    )
    return build_document(meta, profiles={"models": [zams_profile(m, f) for m, f in ZAMS_STARS]})


def main(argv: list[str]) -> None:
    if argv == ["zams"]:
        path = WEB_DATA / "zams.json"
        write_document(zams_document(), path)
        print(f"{path.name}: {path.stat().st_size / 1e3:.0f} kB")
        return
    if argv == ["polytropes"]:
        path = WEB_DATA / "polytropes.json"
        write_document(polytrope_document(), path)
        print(f"{path.name}: {path.stat().st_size / 1e3:.0f} kB")
        return
    if argv != ["web"]:
        raise SystemExit("Run: .venv/bin/python -m stellarforge.export web|polytropes|zams")
    evolution.load_grid()   # once, before forking: the workers share its memory instead of reloading
    with multiprocessing.Pool(4) as pool:  # the machine budget: at most 4 workers
        for line in pool.imap_unordered(_write_web, WEB_FEHS):
            print(line, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
