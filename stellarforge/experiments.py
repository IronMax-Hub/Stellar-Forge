"""Experiments across mass and metallicity: lifetimes, remnants and an IMF population (Phase 3).

Run: .venv/bin/python -m stellarforge.experiments <experiment> [options]
     experiments: lifetime-map, full-life-map, remnant-map, remnant-mass-curves, population,
                  sun-metallicities, all (the six above), zams-extension (Phase 4, ~11 minutes),
                  planet-grid, planet-sensitivity (Phase 5, ~8 and ~2 minutes),
                  planet-surveys (Phase 5 survey checks),
                  planets (all three; with --export also the Planets view's files)
     options: --feh=-4:0.5:0.1   [Fe/H] from:to:step (maps and population)
              --masses=200       log-spaced initial masses, 0.1-300 M☉
              --stars=1000000    stars drawn from the IMF (population)
              --seed=12345       random seed (population)
              --export           also copy result.json to web/public/data/experiments/

Each run writes results/<experiment>/<UTC time>/ with result.json (meta + experiment block; its
`created` is the code's commit time, so the same command on the same code is byte-identical),
figure.png and run.json (command, parameters, machine and wall-clock time).
"""

import json
import os
import platform
import shutil
import sys
import time
from datetime import UTC, datetime
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from . import evolution, export, mist, remnants, structure
from .colour import temperature_to_rgb
from .planets import population as planet_population
from .planets import surveys
from .planets.classify import CLASSES as PLANET_CLASSES

ROOT = Path(__file__).parent.parent
RESULTS = ROOT / "results"
WEB_EXPERIMENTS = export.WEB_DATA / "experiments"
DEFAULTS = {"feh": "-4:0.5:0.1", "masses": 200, "stars": 1_000_000, "seed": 12345}
CURVE_FEHS = (-4.0, -2.0, -1.0, 0.0, 0.5)
SUN_FEHS = (-2.0, -1.0, 0.0, 0.3)
# Kroupa 2001 IMF: dN/dm ∝ m^-1.3 below 0.5 M☉ and m^-2.3 above, drawn over 0.1-100 M☉
KROUPA_BREAK_MSUN, KROUPA_ALPHAS, IMF_RANGE_MSUN = 0.5, (1.3, 2.3), (0.1, 100.0)
CORE_COLLAPSE_FROM_MSUN = 8.0
REMNANT_ORDER = ("white dwarf", "neutron star", "black hole", "none", "not yet", "not predicted")
REFERENCES = ["Choi2016", "Dotter2016", "Paxton2011", "Fryer2012", "Belczynski2016",
              "HegerWoosley2002", "Heger2003", "Cummings2018", "Kroupa2001", "Sana2012"]


# ---- The sweep: one record per (mass, [Fe/H]) ----------------------------------------------

def _cell(mass: float, feh: float) -> dict:
    t = evolution.build_track(mass, feh)
    age = t.values["age_yr"]
    rows = len(age)
    r = remnants.remnant(t, mass)
    ms = rows >= 454   # EEP 202 (ZAMS) to EEP 454 (end of the main sequence)
    return {
        "mass": mass, "feh": feh, "provenance": t.provenance, "ending": t.ending,
        "ms_lifetime_yr": age[453] - age[201] if ms else np.nan,
        # A track that reaches the end of carbon burning has a known total lifetime even where
        # MIST leaves a core mass out; only the remnant needs the core masses.
        "total_lifetime_yr": (age[-1] if t.ending in evolution.FINAL_ENDINGS
                              or t.ending.startswith(evolution.CARBON_END) else np.nan),
        "zams_teff_k": 10 ** t.values["log_teff_k"][201] if rows >= 202 else np.nan,
        "remnant": r.type, "remnant_mass": np.nan if r.mass_msun is None else r.mass_msun,
        "remnant_provenance": r.provenance, "alt_remnant": r.alternative["type"],
        "alt_remnant_mass": (np.nan if r.alternative["mass_msun"] is None
                             else r.alternative["mass_msun"]),
        "he_core": r.he_core_mass_msun,
    }


def _row(args) -> list[dict]:
    feh, masses = args
    return [_cell(float(m), float(feh)) for m in masses]


@lru_cache(maxsize=4)
def sweep(masses: tuple[float, ...], fehs: tuple[float, ...]) -> tuple[list[dict], ...]:
    """Records for every mass at every [Fe/H], one list per [Fe/H], on at most 4 processes."""
    evolution.load_grid()   # once, before forking: the workers share its memory instead of reloading
    with Pool(min(4, len(fehs))) as pool:
        return tuple(pool.map(_row, [(f, masses) for f in fehs]))


def mass_grid(n: int) -> tuple[float, ...]:
    return tuple(float(f"{m:.5g}") for m in np.geomspace(0.1, 300, n))


def feh_grid(spec: str) -> tuple[float, ...]:
    lo, hi, step = (float(x) for x in spec.split(":"))
    return tuple(float(round(f, 2)) for f in np.arange(lo, hi + step / 2, step))


def _ms_word(cell) -> str | None:
    return None if not np.isnan(cell["ms_lifetime_yr"]) else "track incomplete"


def _life_word(cell) -> str | None:
    if not np.isnan(cell["total_lifetime_yr"]):
        return None
    return ("still on the main sequence" if cell["ending"] == evolution.MS_END
            else "track incomplete")


# ---- The six experiments --------------------------------------------------------------------

def lifetime_map(p) -> dict:
    masses, fehs = mass_grid(p["masses"]), feh_grid(p["feh"])
    rows = [export.build_row(label=f"{f:+.1f}", y=f, values=[c["ms_lifetime_yr"] for c in cells],
                             labels=[_ms_word(c) for c in cells],
                             provenance=[c["provenance"] for c in cells])
            for f, cells in zip(fehs, sweep(masses, fehs))]
    return export.build_experiment(
        name="lifetime-map", title="Main-sequence lifetime",
        summary="Time from the zero-age main sequence (EEP 202) to its end (EEP 454), by initial "
                "mass and [Fe/H], from MIST v1.2 tracks.",
        panels=[export.build_panel(
            title="Main-sequence lifetime", kind="heatmap", rows=rows, x_values=masses,
            x_label="Initial mass (M☉)", y_label="[Fe/H]", value_label="years",
            log_x=True, log_values=True)])


def full_life_map(p) -> dict:
    masses, fehs = mass_grid(p["masses"]), feh_grid(p["feh"])
    rows = [export.build_row(label=f"{f:+.1f}", y=f,
                             values=[c["total_lifetime_yr"] for c in cells],
                             labels=[_life_word(c) for c in cells],
                             provenance=[c["provenance"] for c in cells])
            for f, cells in zip(fehs, sweep(masses, fehs))]
    return export.build_experiment(
        name="full-life-map", title="Total lifetime",
        summary="Age at the end of the MIST track for stars whose track reaches a final phase "
                "(the white-dwarf cooling sequence or the end of carbon burning); other cells are "
                "labelled with why there is no total.",
        panels=[export.build_panel(
            title="Total lifetime", kind="heatmap", rows=rows, x_values=masses,
            x_label="Initial mass (M☉)", y_label="[Fe/H]", value_label="years",
            log_x=True, log_values=True)])


def _gap_boundary(fehs, swept, he_core: float) -> list[float]:
    """Lowest initial mass, per [Fe/H], whose final helium core reaches he_core (NaN if none)."""
    out = []
    for cells in swept:
        reached = [c["mass"] for c in cells if c["he_core"] >= he_core
                   and c["ending"].startswith(evolution.CARBON_END)]
        out.append(min(reached) if reached else np.nan)
    return out


def remnant_map(p) -> dict:
    masses, fehs = mass_grid(p["masses"]), feh_grid(p["feh"])
    swept = sweep(masses, fehs)

    def rows(kind, mass):
        return [export.build_row(label=f"{f:+.1f}", y=f, values=[c[mass] for c in cells],
                                 labels=[c[kind] for c in cells],
                                 provenance=[c["remnant_provenance"] for c in cells])
                for f, cells in zip(fehs, swept)]

    gap = [export.build_row(label=label, values=_gap_boundary(fehs, swept, he),
                            provenance=["predicted"] * len(fehs))
           for label, he in (("helium core ≥ 45 M☉: pulsational pair instability",
                              remnants.PPSN_HE_CORE_MSUN),
                             ("helium core ≥ 65 M☉: pair-instability supernova",
                              remnants.PISN_HE_CORE_MSUN))]
    return export.build_experiment(
        name="remnant-map", title="Remnants",
        summary="The remnant each star leaves, under Fryer et al. 2012's delayed and rapid "
                "prescriptions with Belczynski et al. 2016's pair instability, and the lowest "
                "initial mass that reaches the pair-instability ranges at each [Fe/H] (a "
                "Stellar-Forge result with no published target).",
        panels=[
            export.build_panel(title="Remnant, delayed (adopted)", kind="heatmap",
                               rows=rows("remnant", "remnant_mass"), x_values=masses,
                               x_label="Initial mass (M☉)", y_label="[Fe/H]",
                               value_label="remnant mass (M☉)", log_x=True),
            export.build_panel(title="Remnant, rapid (alternative)", kind="heatmap",
                               rows=rows("alt_remnant", "alt_remnant_mass"), x_values=masses,
                               x_label="Initial mass (M☉)", y_label="[Fe/H]",
                               value_label="remnant mass (M☉)", log_x=True),
            export.build_panel(title="Lowest initial mass reaching the pair-instability ranges",
                               kind="curves", rows=gap, x_values=fehs, x_label="[Fe/H]",
                               y_label="Initial mass (M☉)", value_label="M☉", log_values=True),
        ])


def remnant_mass_curves(p) -> dict:
    masses = mass_grid(p["masses"])
    swept = sweep(masses, CURVE_FEHS)

    def panel(title, key):
        # One curve per [Fe/H], in the same order (and so the same colours) in both panels
        rows = [export.build_row(label=f"[Fe/H] {f:+.1f}", y=f, values=[c[key] for c in cells],
                                 provenance=[c["remnant_provenance"] for c in cells])
                for f, cells in zip(CURVE_FEHS, swept)]
        return export.build_panel(
            title=title, kind="curves", rows=rows, x_values=masses, x_label="Initial mass (M☉)",
            y_label="Remnant mass (M☉)", value_label="M☉", log_x=True, log_values=True)

    return export.build_experiment(
        name="remnant-mass-curves", title="Remnant mass against initial mass",
        summary="Remnant mass under both Fryer et al. 2012 prescriptions at five metallicities; "
                "gaps are stars with no remnant (destroyed, not yet, or not predicted).",
        panels=[panel("Remnant mass, delayed (adopted)", "remnant_mass"),
                panel("Remnant mass, rapid (alternative)", "alt_remnant_mass")])


def kroupa_sample(n: int, seed: int) -> np.ndarray:
    """n initial masses from the Kroupa 2001 IMF over 0.1-100 M☉, by inverting its CDF."""
    (lo, hi), brk, (a1, a2) = IMF_RANGE_MSUN, KROUPA_BREAK_MSUN, KROUPA_ALPHAS

    def integral(a, b, alpha):   # ∫ m^-alpha dm from a to b
        return (b ** (1 - alpha) - a ** (1 - alpha)) / (1 - alpha)

    # Continuous at the break: the upper segment is scaled by brk^(a2 - a1)
    w1, w2 = integral(lo, brk, a1), brk ** (a2 - a1) * integral(brk, hi, a2)
    u = np.random.default_rng(seed).random(n) * (w1 + w2)
    low = u < w1
    out = np.empty(n)
    out[low] = (lo ** (1 - a1) + (1 - a1) * u[low]) ** (1 / (1 - a1))
    out[~low] = (brk ** (1 - a2) + (1 - a2) * (u[~low] - w1) / brk ** (a2 - a1)) ** (1 / (1 - a2))
    return out


def population(p) -> dict:
    fehs = feh_grid(p["feh"])
    masses = tuple(m for m in mass_grid(p["masses"]) if m <= IMF_RANGE_MSUN[1])
    stars = kroupa_sample(p["stars"], p["seed"])
    # Each star takes the remnant of the nearest swept mass in log mass
    edges = np.sqrt(np.array(masses[:-1]) * np.array(masses[1:]))
    nearest = np.searchsorted(edges, stars)
    count = np.bincount(nearest, minlength=len(masses))
    total_mass = stars.sum()
    shares = {kind: [] for kind in REMNANT_ORDER}
    collapse = []
    for cells in sweep(masses, fehs):
        kinds = np.array([c["remnant"] for c in cells])
        for kind in REMNANT_ORDER:
            shares[kind].append(100 * count[kinds == kind].sum() / len(stars))
        collapse.append(1000 * count[np.isin(kinds, ("neutron star", "black hole"))].sum()
                        / total_mass)
    above = 100 * np.mean(stars > CORE_COLLAPSE_FROM_MSUN)
    return export.build_experiment(
        name="population", title="A stellar population's remnants",
        summary=(f"{len(stars):,} stars drawn from the Kroupa 2001 IMF over 0.1–100 M☉ "
                 f"(seed {p['seed']}); each takes the adopted remnant of the nearest swept mass. "
                 f"{above:.3f}% are born above 8 M☉. Shares are by number of stars; 'not "
                 "predicted' marks MIST tracks that stop too early."),
        panels=[
            export.build_panel(
                title="Share of stars ending as each remnant", kind="curves", x_values=fehs,
                x_label="[Fe/H]", y_label="Share of stars (%)", value_label="%",
                rows=[export.build_row(label=k, values=shares[k],
                                       provenance=["predicted"] * len(fehs))
                      for k in REMNANT_ORDER]),
            export.build_panel(
                title="Core collapses (neutron stars and black holes) per 1,000 M☉ formed",
                kind="curves", x_values=fehs, x_label="[Fe/H]", y_label="per 1,000 M☉",
                value_label="per 1,000 M☉",
                rows=[export.build_row(label="core collapses", values=collapse,
                                       provenance=["predicted"] * len(fehs))]),
        ])


def sun_metallicities(p) -> dict:
    cells = [c for row in sweep((1.0,), SUN_FEHS) for c in row]
    columns = ["Main-sequence lifetime (Gyr)", "Total lifetime (Gyr)", "T_eff at ZAMS (K)",
               "Colour at ZAMS (sRGB)", "Remnant", "Remnant mass (M☉)"]
    rows = []
    for c in cells:
        rgb = ", ".join(f"{x:.3f}" for x in temperature_to_rgb(c["zams_teff_k"]))
        rows.append(export.build_row(
            label=f"[Fe/H] {c['feh']:+.1f}", y=c["feh"],
            values=[c["ms_lifetime_yr"] / 1e9, c["total_lifetime_yr"] / 1e9, c["zams_teff_k"],
                    np.nan, np.nan, c["remnant_mass"]],
            labels=[_ms_word(c), _life_word(c), None, rgb, c["remnant"], None],
            provenance=[c["provenance"], c["provenance"], c["provenance"], "derived",
                        c["remnant_provenance"], c["remnant_provenance"]]))
    return export.build_experiment(
        name="sun-metallicities", title="The Sun at other metallicities",
        summary="A 1 M☉ star at [Fe/H] −2, −1, 0 and +0.3: lifetimes, colour on the zero-age "
                "main sequence and remnant.",
        panels=[export.build_panel(title="1 M☉ at four metallicities", kind="table", rows=rows,
                                   columns=columns)])


EXPERIMENTS = {"lifetime-map": lifetime_map, "full-life-map": full_life_map,
               "remnant-map": remnant_map, "remnant-mass-curves": remnant_mass_curves,
               "population": population, "sun-metallicities": sun_metallicities}


# ---- Phase 4: the zero-age solver from 0.8 to 20 M☉ (milestone 6, a goal) ----------------------

EXTENSION_FEHS = (-1.0, 0.0, 0.25)
# 30 MIST grid masses nearest to 30 log-spaced values over 0.8-20 M☉, so each model is compared with
# a published track rather than an interpolated one
EXTENSION_MASSES = (0.8, 0.9, 1.0, 1.12, 1.24, 1.4, 1.56, 1.74, 1.94, 2.18, 2.42, 2.72, 3.0, 3.4,
                    3.8, 4.2, 4.8, 5.2, 5.8, 6.6, 7.4, 8.0, 9.0, 10.0, 11.0, 13.0, 14.0, 16.0,
                    18.0, 20.0)
GATE = {"log_l_lsun": 0.1, "log_r_rsun": 0.1, "log_t_c_k": 0.05}   # dex, the Phase 4 tolerances
MIST_STOPS_AT_ZAMS = "MIST track stops at the zero-age EEP"
MIST_BURNED = 0.05      # central hydrogen burned before MIST's burning and core are read
CORE_FROM = 0.02        # a convective core counts from this share of the star's mass


def _zams_cell(args) -> dict:
    """One star: from MIST's zero-age star, or from `guess` (P_c, T_c, R, L) when given."""
    mass, feh, *rest = args
    guess = rest[0] if rest else None
    start = time.perf_counter()
    cell = {"mass": mass, "feh": feh, "converged": False, "error": None, "start": "MIST"}
    if evolution.build_track(mass, feh).ending == "zero-age main sequence":
        # The MIST track stops at EEP 202 (16 M☉ at [Fe/H] +0.25, still contracting there): no
        # zero-age star to compare with, so the star is labelled, not solved
        return cell | {"error": MIST_STOPS_AT_ZAMS, "seconds": 0.0}
    mz = structure.mist_zams(mass, feh)
    try:
        model = structure.solve_zams(mass, feh, composition=mz.composition, guess=guess)
    except (RuntimeError, ValueError, FloatingPointError) as e:
        cell["error"] = str(e)
    else:
        q = structure.profile_quantities(model)
        pp, cno = np.trapezoid(q["eps_pp_w_kg"], model.m_kg), np.trapezoid(q["eps_cno_w_kg"],
                                                                         model.m_kg)
        conv = q["convective"]
        core = model.m_kg[np.argmin(conv)] / model.m_kg[-1] if conv[0] else 0.0
        cell |= {"converged": True,
                 "solution": (model.p_c_pa, model.t_c_k, model.radius_rsun,
                              model.luminosity_lsun),
                 "delta_log_l_lsun": np.log10(model.luminosity_lsun) - mz.log_l_lsun,
                 "delta_log_r_rsun": np.log10(model.radius_rsun) - mz.log_r_rsun,
                 "delta_log_t_c_k": np.log10(model.t_c_k) - mz.log_t_c_k,
                 "pp_share": pp / (pp + cno), "conv_core_frac": core}
    cell["seconds"] = time.perf_counter() - start
    return cell


def _crossing(masses, values, level: float) -> float:
    """The first mass where values reach `level`, interpolated in log mass (NaN if never)."""
    v = np.asarray(values, dtype=float)
    for k in range(1, len(v)):
        a, b = v[k - 1], v[k]
        if np.isfinite(a) and np.isfinite(b) and (a - level) * (b - level) <= 0 and a != b:
            w = (level - a) / (b - a)
            return float(np.exp((1 - w) * np.log(masses[k - 1]) + w * np.log(masses[k])))
    return np.nan


def zams_extension(p) -> dict:
    masses, fehs = EXTENSION_MASSES, EXTENSION_FEHS
    with Pool(4) as pool:   # the machine budget: at most 4 workers
        flat = pool.map(_zams_cell, [(m, f) for f in fehs for m in masses], chunksize=1)
    cells = [flat[i * len(masses):(i + 1) * len(masses)] for i in range(len(fehs))]
    # A star that fails from MIST's values is retried from each converged neighbour's solution in
    # turn (the nearer mass first), on the same 4 workers
    retries = []
    for row in cells:
        for k, c in enumerate(row):
            if not c["converged"] and c.get("error") != MIST_STOPS_AT_ZAMS:
                near = sorted((j for j, d in enumerate(row) if d["converged"]),
                              key=lambda j: abs(np.log(masses[j] / masses[k])))[:2]
                retries.append((row, k, near))
    with Pool(4) as pool:
        tried = pool.map(_zams_cell, [(masses[k], row[k]["feh"], row[j]["solution"])
                                      for row, k, near in retries for j in near], chunksize=1)
    i = 0
    for row, k, near in retries:
        for j in near:
            if tried[i]["converged"] and not row[k]["converged"]:
                row[k] = tried[i] | {"start": f"the converged {masses[j]} M☉ solution"}
            i += 1
    # MIST's own pp and CNO luminosities (log10 L☉) and convective-core mass. At EEP 202 MIST's
    # lower-mass stars still burn their initial carbon-12 and helium-3 out of equilibrium, with a
    # transient convective core at every mass, so these are read once 5% of the central hydrogen
    # has burned (central X down by MIST_BURNED from EEP 202): by then the transient cores below
    # ~1.1 M☉ have mostly gone and the pp share has barely moved from its zero-age value.
    mist_rows = {}
    for f in fehs:
        tracks = mist.eep_columns(mist.CACHE / f"MIST_v1.2_feh_{'m' if f < 0 else 'p'}"
                                               f"{abs(f):.2f}_afe_p0.0_vvcrit0.4_EEPS.txz",
                                  ("pp", "cno", "mass_conv_core", "center_h1"))
        mist_rows[f] = {}
        for m in masses:
            t = tracks[m]
            k = int(np.argmax(t["center_h1"] <= t["center_h1"][0] - MIST_BURNED))
            mist_rows[f][m] = {n: float(t[n][k]) for n in ("pp", "cno", "mass_conv_core")}

    def value(c, key):
        return c[key] if c["converged"] else np.nan

    def word(c):
        if c["converged"]:
            return None
        return MIST_STOPS_AT_ZAMS if c.get("error") == MIST_STOPS_AT_ZAMS else "did not converge"

    def delta_panel(key, title):
        rows = [export.build_row(label=f"[Fe/H] {f:+.2f}", y=f, values=[value(c, key) for c in row],
                                 labels=[word(c) for c in row], provenance=["derived"] * len(row))
                for f, row in zip(fehs, cells)]
        return export.build_panel(
            title=f"{title}: model − MIST (gate ±{GATE[key.removeprefix('delta_')]} dex)",
            kind="curves", rows=rows, x_values=masses, x_label="Initial mass (M☉)",
            y_label="model − MIST (dex)", value_label="dex", log_x=True)

    mist_pp = {f: [10 ** mist_rows[f][m]["pp"] / (10 ** mist_rows[f][m]["pp"]
                                                   + 10 ** mist_rows[f][m]["cno"]) for m in masses]
               for f in fehs}
    mist_core = {f: [mist_rows[f][m]["mass_conv_core"] / m for m in masses] for f in fehs}

    def compare_panel(title, y_label, key, mist_values):
        rows = []
        for f, row in zip(fehs, cells):
            rows.append(export.build_row(label=f"model [Fe/H] {f:+.2f}", y=f,
                                         values=[value(c, key) for c in row],
                                         labels=[word(c) for c in row],
                                         provenance=["derived"] * len(row)))
            # Shares and ratios computed here from MIST's published columns: derived
            rows.append(export.build_row(label=f"MIST [Fe/H] {f:+.2f}", y=f, values=mist_values[f],
                                         provenance=["derived"] * len(masses)))
        return export.build_panel(title=title, kind="curves", rows=rows, x_values=masses,
                                  x_label="Initial mass (M☉)", y_label=y_label, value_label="",
                                  log_x=True)

    columns = ["Masses converged", "Largest |Δ log L| (dex)", "Largest |Δ log R| (dex)",
               "Largest |Δ log Tc| (dex)", "Masses within the gate",
               "pp = CNO at (M☉), model", "pp = CNO at (M☉), MIST",
               "Convective core from (M☉), model", "Convective core from (M☉), MIST"]
    table = []
    for f, row in zip(fehs, cells):
        ok = [c for c in row if c["converged"]]
        within = sum(all(abs(c[f"delta_{k}"]) <= tol for k, tol in GATE.items()) for c in ok)
        worst = [max((abs(c[f"delta_{k}"]) for c in ok), default=np.nan) for k in GATE]
        table.append(export.build_row(
            label=f"[Fe/H] {f:+.2f}", y=f,
            values=[len(ok), *worst, within,
                    _crossing(masses, [value(c, "pp_share") for c in row], 0.5),
                    _crossing(masses, mist_pp[f], 0.5),
                    _crossing(masses, [value(c, "conv_core_frac") > CORE_FROM if c["converged"]
                                       else np.nan for c in row], 0.5),
                    _crossing(masses, [v > CORE_FROM for v in mist_core[f]], 0.5)],
            provenance=["derived"] * 9))   # MIST's crossings are interpolated here, so derived
    failed = [f"{c['mass']} M☉ at [Fe/H] {c['feh']:+.2f}" for row in cells for c in row
              if not c["converged"] and c.get("error") != MIST_STOPS_AT_ZAMS]
    no_mist = [f"{c['mass']} M☉ at [Fe/H] {c['feh']:+.2f}" for row in cells for c in row
               if c.get("error") == MIST_STOPS_AT_ZAMS]
    rescued = [f"{c['mass']} M☉ at [Fe/H] {c['feh']:+.2f} (from {c['start']})" for row in cells
               for c in row if c["converged"] and c["start"] != "MIST"]
    return export.build_experiment(
        name="zams-extension", title="Zero-age stars from 0.8 to 20 M☉ against MIST",
        summary=(f"The Phase 4 structure solver (milestone 5 physics) at {len(masses)} MIST grid "
                 f"masses and [Fe/H] {', '.join(f'{f:+.2f}' for f in fehs)}, compared with MIST's "
                 "zero-age EEP 202 using each archive's X, Y and Z. A goal, not a gate: masses that "
                 "fail to converge are reported, not forced. "
                 + (f"Did not converge: {'; '.join(failed)}." if failed else
                    "Every mass converged.")
                 + (f" Not compared, as the MIST track stops at EEP 202: {'; '.join(no_mist)}."
                    if no_mist else "")
                 + (f" Converged only when started from a neighbour's solution: "
                    f"{'; '.join(rescued)}." if rescued else "")
                 + " MIST's pp, CNO and convective-core values are read once 5% of the central "
                 "hydrogen has burned: at EEP 202 its lower-mass stars still burn carbon-12 and "
                 "helium-3 out of equilibrium, with transient convective cores. Crossings are "
                 "interpolated in log mass between grid masses; a convective core counts from 2% "
                 "of the star's mass, in the model and in MIST."),
        panels=[delta_panel("delta_log_l_lsun", "Luminosity"),
                delta_panel("delta_log_r_rsun", "Radius"),
                delta_panel("delta_log_t_c_k", "Central temperature"),
                compare_panel("pp chain's share of the energy (MIST after 5% of central H burned)",
                              "pp / (pp + CNO)", "pp_share", mist_pp),
                compare_panel("Convective core (MIST after 5% of central H burned)",
                              "convective-core mass / M", "conv_core_frac", mist_core),
                export.build_panel(title="Summary per metallicity", kind="table", rows=table,
                                   columns=columns)])


STRUCTURE_EXPERIMENTS = {"zams-extension": zams_extension}


# ---- Phase 5: planet populations --------------------------------------------------------------

PLANET_MASSES = tuple(float(f"{m:.3g}") for m in np.geomspace(0.2, 1.5, 8))
PLANET_FEHS = (-4.0, -3.0, -2.0, -1.5, -1.0, -0.75, -0.5, -0.375, -0.25, -0.125, 0.0, 0.125, 0.25,
               0.375, 0.5)
PLANET_SYSTEMS = 5000
PLANET_SEED = 20261114
CALIBRATED_MSUN, CALIBRATED_FEH = (0.2, 1.5), (-0.5, 0.5)   # Ida & Lin 2005; survey coverage
# Variants for the sensitivity runs: one change from the defaults each (build plan, step 4)
SENSITIVITY = {"defaults": {}, "C1 = 0.03": {"c1": 0.03}, "C1 = 0.3": {"c1": 0.3},
               "τ_disk 0.5-5 Myr": {"tau_disk_range_yr": (5e5, 5e6)},
               "τ_disk 2-20 Myr": {"tau_disk_range_yr": (2e6, 2e7)},
               "f_g spread 0.5 dex": {"f_g_sigma_dex": 0.5},
               "f_g spread 1.5 dex": {"f_g_sigma_dex": 1.5},
               "disk mass ∝ M★²": {"disk_mass_scaling": "ida-lin"}}
SENSITIVITY_CELLS = ((1.0, -0.5), (1.0, 0.0), (1.0, 0.3), (0.5, 0.0))


SAMPLE_SYSTEMS = 200     # exported per cell for the Planets view (build plan, step 5)
WEB_PLANETS = export.WEB_DATA / "planets"


def _planet_stats(args) -> dict:
    """One cell's statistics: the share of systems hosting each class, planets per star, how many
    systems have each number of planets and, for the default parameters, the first SAMPLE_SYSTEMS
    systems (an unbiased sample: the disks are drawn at random)."""
    m_star, feh, n, seed, params = args
    survey_only = params.get("survey_only", False)
    params = {k: v for k, v in params.items() if k != "survey_only"}
    cell = planet_population.run_cell(m_star, feh, n, seed, **params)
    p = cell["planets"]
    hosts = {k: np.unique(p["system"][p["class"] == k]).size / n for k in PLANET_CLASSES}
    out = {"m_star": m_star, "feh": feh, "seed": seed, "n": n, "hosts": hosts,
           "per_star": len(p["system"]) / n, "a_ice": cell["a_ice_au"],
           "counts": np.bincount(np.bincount(p["system"], minlength=n)).tolist(),
           "survey": surveys.survey_stats(p, n, m_star, seed=seed)}
    if not params and not survey_only:
        d = cell["disks"]
        out["samples"] = [
            {"index": i, "f_g0": d["f_g0"][i], "f_d0": d["f_d0"][i],
             "tau_disk_yr": d["tau_disk_yr"][i],
             "planets": [export.build_planet(
                 planet_class=str(p["class"][j]), mass_mearth=p["mass_mearth"][j],
                 radius_rearth=p["radius_rearth"][j], a_au=p["a_au"][j],
                 a_form_au=p["a_form_au"][j], f_env=p["f_env"][j], ice_rich=bool(p["ice_rich"][j]))
                 for j in np.flatnonzero(p["system"] == i)]}
            for i in range(min(SAMPLE_SYSTEMS, n))]
    return out


def _calibrated(m_star: float, feh: float) -> bool:
    return (CALIBRATED_MSUN[0] <= m_star <= CALIBRATED_MSUN[1]
            and CALIBRATED_FEH[0] <= feh <= CALIBRATED_FEH[1])


@lru_cache(maxsize=1)
def planet_grid_cells() -> tuple[tuple[dict, ...], ...]:
    """Every grid cell, [Fe/H]-major, run once per process on 4 workers."""
    jobs = [(m, f, PLANET_SYSTEMS, PLANET_SEED + i, {})
            for i, (f, m) in enumerate((f, m) for f in PLANET_FEHS for m in PLANET_MASSES)]
    with Pool(4) as pool:   # the machine budget: at most 4 workers
        flat = pool.map(_planet_stats, jobs, chunksize=1)
    return tuple(tuple(flat[i * len(PLANET_MASSES):(i + 1) * len(PLANET_MASSES)])
                 for i in range(len(PLANET_FEHS)))


@lru_cache(maxsize=1)
def planet_sensitivity_cells() -> dict[str, tuple[dict, ...]]:
    """The key cells under each sensitivity variant, the same seed per cell in every variant."""
    jobs = [(m, f, PLANET_SYSTEMS, PLANET_SEED + k, params)
            for params in SENSITIVITY.values() for k, (m, f) in enumerate(SENSITIVITY_CELLS)]
    with Pool(4) as pool:
        flat = pool.map(_planet_stats, jobs, chunksize=1)
    n = len(SENSITIVITY_CELLS)
    return {name: tuple(flat[i * n:(i + 1) * n]) for i, name in enumerate(SENSITIVITY)}


def planet_conclusions() -> list[dict]:
    """Statements about the population, each labelled `prediction` when it holds under every
    sensitivity variant and `parameter-sensitive` otherwise."""
    runs = planet_sensitivity_cells()
    giants = {name: [c["hosts"]["gas giant"] for c in cells] for name, cells in runs.items()}
    rises = [g[0] < g[1] < g[2] for g in giants.values()]
    fewer = [g[3] < g[1] for g in giants.values()]
    solar = [g[1] for g in giants.values()]
    m_dwarf = [g[3] for g in giants.values()]

    def label(holds):
        return "prediction" if all(holds) else "parameter-sensitive"
    return [
        {"statement": "Gas giants become more common as [Fe/H] rises (1 M☉: -0.5, 0.0, +0.3)",
         "label": label(rises)},
        {"statement": "Gas giants are rarer around 0.5 M☉ stars than around 1 M☉ stars at solar "
                      "[Fe/H]", "label": label(fewer)},
        {"statement": f"Share of 1 M☉, solar-[Fe/H] systems with a gas giant: {min(solar):.2f}-"
                      f"{max(solar):.2f} across the sensitivity runs",
         "label": "parameter-sensitive" if max(solar) - min(solar) > 0.05 else "prediction"},
        {"statement": f"Share of 0.5 M☉, solar-[Fe/H] systems with a gas giant: {min(m_dwarf):.3f}"
                      f"-{max(m_dwarf):.3f} across the sensitivity runs",
         "label": "parameter-sensitive" if max(m_dwarf) - min(m_dwarf) > 0.05 else "prediction"}
    ] + [{"statement": f"Survey check, {c['name']}: model {c['model']:.3g}, survey {c['survey']:.3g} "
                       f"({c['source']}; {c['tolerance']}): {'pass' if c['passed'] else 'fail'}",
          "label": "observational constraint"} for c in planet_survey_checks()]


def planet_grid(p) -> dict:
    rows = planet_grid_cells()

    def heat(title, value, label, log=False):
        return export.build_panel(
            title=title, kind="heatmap", x_values=PLANET_MASSES, x_label="Star mass (M☉)",
            y_label="[Fe/H]", value_label=label, log_x=True, log_values=log,
            rows=[export.build_row(label=f"{f:+.3g}", y=f, values=[value(c) for c in row],
                                   provenance=["predicted"] * len(row))
                  for f, row in zip(PLANET_FEHS, rows)])
    sun = int(np.argmin(np.abs(np.log(np.array(PLANET_MASSES)))))
    return export.build_experiment(
        name="planet-grid", title="Planet populations by star mass and metallicity",
        summary=(f"Ida & Lin's population synthesis (Paper VII gas phase, 2008a seeding): "
                 f"{PLANET_SYSTEMS:,} disks per cell, 15 seeds each, seeds {PLANET_SEED}+cell "
                 f"index. Defaults: C1 = {planet_population.C1_DEFAULT}, α = "
                 f"{planet_population.ALPHA_DEFAULT:g}, disk mass ∝ M★, f_g spread 1 dex, τ_disk "
                 "1-10 Myr. Planets are bodies of at least "
                 f"{planet_population.M_MIN_PLANET} M⊕ after giant impacts to 1 Gyr (Ida & Lin 2004a "
                 "eq. 24 within each seed's annulus; orbit crossing and mergers between seeds, "
                 "Ida & Lin 2010); migrating embryos park in resonant convoys from 0.04 AU. Inside the calibration range (0.2-1.5 M☉, [Fe/H] "
                 "-0.5 to +0.5) cells are predictions; below [Fe/H] -0.5 they are extrapolations. "
                 "Survey comparisons are in the planet-surveys experiment."),
        panels=[heat("Systems with a gas giant", lambda c: c["hosts"]["gas giant"], "share"),
                heat("Planets per star (≥ 0.1 M⊕)", lambda c: c["per_star"], "planets"),
                export.build_panel(
                    title=f"Systems hosting each class around a {PLANET_MASSES[sun]} M☉ star",
                    kind="curves", x_values=PLANET_FEHS, x_label="[Fe/H]", y_label="share",
                    value_label="share",
                    rows=[export.build_row(label=k, values=[r[sun]["hosts"][k] for r in rows],
                                           provenance=["predicted"] * len(rows))
                          for k in PLANET_CLASSES])])


def planet_sensitivity(p) -> dict:
    runs = planet_sensitivity_cells()
    rows, holds = [], {}
    for name, cells in runs.items():
        g = [c["hosts"]["gas giant"] for c in cells]
        rises = g[0] < g[1] < g[2]          # more giants at higher [Fe/H] (1 M☉)
        fewer = g[3] < g[1]                 # fewer giants around 0.5 M☉ than 1 M☉
        holds[name] = (rises, fewer)
        n = len(cells)
        rows.append(export.build_row(
            label=name, values=[*g, cells[1]["per_star"], np.nan, np.nan],
            labels=[None] * (n + 1) + ["yes" if rises else "no", "yes" if fewer else "no"],
            provenance=["predicted"] * (n + 1) + [None, None]))
    columns = [f"giant share {m} M☉ {f:+.1f}" for m, f in SENSITIVITY_CELLS] + [
        "planets/star 1 M☉ 0.0", "giants rise with [Fe/H]", "fewer giants at 0.5 M☉"]
    robust = [c for c, k in (("giants rise with [Fe/H]", 0), ("fewer giants at 0.5 M☉", 1))
              if all(h[k] for h in holds.values())]
    return export.build_experiment(
        name="planet-sensitivity", title="Which planet-population conclusions survive the "
                                         "parameter changes",
        summary=(f"Each row changes one default; {PLANET_SYSTEMS:,} disks per cell, the same seed "
                 "per cell in every row. Conclusions that hold in every row: "
                 + (", ".join(robust) if robust else "none") + ". The rest are parameter-sensitive."),
        panels=[export.build_panel(title="Sensitivity runs", kind="table", rows=rows,
                                   columns=columns)])


SURVEY_FEHS = (-0.5, -0.4, -0.25, 0.0, 0.25, 0.4, 0.5)   # 1 M☉, for the survey slopes


@lru_cache(maxsize=1)
def planet_survey_cells() -> tuple[dict, ...]:
    """A solar-mass star at the surveys' metallicities (1 M☉ is not on the grid)."""
    jobs = [(1.0, f, PLANET_SYSTEMS, PLANET_SEED + 1000 + k, {"survey_only": True})
            for k, f in enumerate(SURVEY_FEHS)]
    with Pool(4) as pool:
        return tuple(pool.map(_planet_stats, jobs, chunksize=1))


def planet_survey_checks() -> list[dict]:
    """Each Validation check: the model's number, the survey's, the tolerance and pass or fail."""
    one = {c["feh"]: c["survey"] for c in planet_survey_cells()}
    solar_row = planet_grid_cells()[PLANET_FEHS.index(0.0)]
    by_mass = [(c["m_star"], c["survey"]) for c in solar_row if c["m_star"] >= 0.45]
    giants = [one[f]["rv_giant_share"] for f in SURVEY_FEHS]
    beta = surveys.slope(SURVEY_FEHS, giants)
    alpha = surveys.slope(np.log10([m for m, _ in by_mass]), [s["rv_giant_share"] for _, s in by_mass])
    low = by_mass[0]
    twin = one[0.0]["rv_giant_share"]
    warm = [f for f in SURVEY_FEHS if abs(f) <= 0.4]
    se = one[0.0]["warm_super_earths_per_100"]
    se_beta = surveys.slope(warm, [one[f]["warm_super_earths_per_100"] for f in warm])
    sn_ratio = one[0.4]["warm_sub_neptunes_per_100"] / max(one[-0.4]["warm_sub_neptunes_per_100"], 1e-9)
    b_lo, b_hi = surveys.BETA_GIANT_RANGE
    a_lo, a_hi = surveys.ALPHA_RANGE
    se_lo = surveys.PETIGURA_SE_BETA - surveys.SE_BETA_SIGMA * surveys.PETIGURA_SE_BETA_ERR
    se_hi = surveys.PETIGURA_SE_BETA + surveys.SE_BETA_SIGMA * surveys.PETIGURA_SE_BETA_ERR

    def check(name, model, survey, tolerance, passed, source):
        return {"name": name, "model": model, "survey": survey, "tolerance": tolerance,
                "passed": bool(passed), "source": source}
    return [
        check("Giant planets against [Fe/H]: slope β of log share (1 M☉, -0.5 to +0.5)", beta,
              surveys.FISCHER_VALENTI_BETA, f"{b_lo:.1f} ≤ β ≤ {b_hi:.1f} (between the two surveys, "
              "±0.4)", b_lo <= beta <= b_hi, "Fischer & Valenti 2005; Johnson et al. 2010"),
        check(f"Giant planets against star mass: exponent α ({by_mass[0][0]}-{by_mass[-1][0]} M☉, "
              "solar [Fe/H])", alpha, surveys.JOHNSON_ALPHA,
              f"{a_lo} ≤ α ≤ {a_hi}", a_lo <= alpha <= a_hi, "Johnson et al. 2010"),
        check(f"Giant share at {low[0]} M☉, solar [Fe/H]", low[1]["rv_giant_share"],
              surveys.JOHNSON_AT[0.5], "within a factor 2 of 3.5%",
              0.5 <= low[1]["rv_giant_share"] / surveys.JOHNSON_AT[0.5] <= 2,
              "Johnson et al. 2010"),
        check("Solar twin: share with a 0.3-10 M_J planet at P = 2-2,000 d", twin,
              surveys.CUMMING_SHARE, f"within a factor {surveys.TWIN_FACTOR} of 10.5%",
              1 / surveys.TWIN_FACTOR <= twin / surveys.CUMMING_SHARE <= surveys.TWIN_FACTOR,
              "Cumming et al. 2008"),
        check("Warm super-Earths per 100 stars (1.0-1.7 R⊕, 10-100 d), solar [Fe/H]", se,
              surveys.PETIGURA_SE_PER_100, f"within a factor {surveys.SE_LEVEL_FACTOR:g} of 20",
              1 / surveys.SE_LEVEL_FACTOR <= se / surveys.PETIGURA_SE_PER_100
              <= surveys.SE_LEVEL_FACTOR, "Petigura et al. 2018"),
        check("Warm super-Earths against [Fe/H]: slope β (-0.4 to +0.4)", se_beta,
              surveys.PETIGURA_SE_BETA, f"{se_lo:.1f} ≤ β ≤ {se_hi:.1f} (2σ)",
              se_lo <= se_beta <= se_hi, "Petigura et al. 2018"),
        check("Warm sub-Neptunes (1.7-4.0 R⊕): ratio from [Fe/H] -0.4 to +0.4", sn_ratio, 2.0,
              "≥ √2 (at least half of the survey's doubling, in log)", sn_ratio >= np.sqrt(2),
              "Petigura et al. 2018; Buchhave et al. 2012"),
    ]


def planet_surveys(p) -> dict:
    checks = planet_survey_checks()
    one = {c["feh"]: c["survey"] for c in planet_survey_cells()}
    solar_row = planet_grid_cells()[PLANET_FEHS.index(0.0)]
    rows = [export.build_row(label=c["name"], values=[c["model"], c["survey"], np.nan],
                             labels=[None, None, "pass" if c["passed"] else "fail"],
                             provenance=["predicted", None, None]) for c in checks]
    passed = sum(c["passed"] for c in checks)
    return export.build_experiment(
        name="planet-surveys", title="The planet population against surveys",
        summary=(f"{passed} of {len(checks)} checks pass. The model's planets are cut as each survey "
                 "cuts its own (mass and period for radial-velocity giants, Chen & Kipping radius and "
                 "period for Kepler's small planets); surveys check the model and never enter it. "
                 "Tolerances are Stellar-Forge choices: "
                 + "; ".join(f"{c['source']}: {c['tolerance']}" for c in checks) + "."),
        panels=[
            export.build_panel(title="Survey checks", kind="table", rows=rows,
                               columns=["model", "survey", "result"]),
            export.build_panel(
                title="Share of 1 M☉ systems with a 0.3-10 M_J planet at P = 2-2,000 d",
                kind="curves", x_values=SURVEY_FEHS, x_label="[Fe/H]", y_label="share",
                value_label="share", log_values=True,
                rows=[export.build_row(label="any composition (as surveys see it)",
                                       values=[one[f]["rv_giant_share"] for f in SURVEY_FEHS],
                                       provenance=["predicted"] * len(SURVEY_FEHS)),
                      export.build_row(label="gas giants only (f_env ≥ 0.5)",
                                       values=[one[f]["rv_giant_share_gas_giants"]
                                               for f in SURVEY_FEHS],
                                       provenance=["predicted"] * len(SURVEY_FEHS)),
                      export.build_row(label="Fischer & Valenti 2005 shape, through the model at 0.0",
                                       values=[one[0.0]["rv_giant_share"] * 10 ** (2 * f)
                                               for f in SURVEY_FEHS],
                                       provenance=["derived"] * len(SURVEY_FEHS))]),
            export.build_panel(
                title="The same cut by star mass, solar [Fe/H]", kind="curves",
                x_values=PLANET_MASSES, x_label="Star mass (M☉)", y_label="share",
                value_label="share", log_x=True,
                rows=[export.build_row(label="any composition",
                                       values=[c["survey"]["rv_giant_share"] for c in solar_row],
                                       provenance=["predicted"] * len(solar_row)),
                      export.build_row(label="gas giants only",
                                       values=[c["survey"]["rv_giant_share_gas_giants"]
                                               for c in solar_row],
                                       provenance=["predicted"] * len(solar_row))])])


def export_planets(meta: dict) -> Path:
    """The Planets view's files: planets/population.json and one systems file per cell."""
    cells, flat = [], [c for row in planet_grid_cells() for c in row]
    # Survey failures are model limits, so every cell carries them (ground rule 6)
    failed = [f"survey_check_failed: {c['name']}: model {c['model']:.3g}, survey {c['survey']:.3g} "
              f"({c['source']})" for c in planet_survey_checks() if not c["passed"]]
    for i, c in enumerate(flat):
        calibration = "prediction" if _calibrated(c["m_star"], c["feh"]) else "extrapolation"
        name = f"systems_{i:03d}.json"
        export.write_document(export.build_document(meta, systems=export.build_systems(
            m_star_msun=c["m_star"], feh=c["feh"], seed=c["seed"], calibration=calibration,
            a_ice_au=c["a_ice"], systems=c["samples"])), WEB_PLANETS / name)
        cells.append(export.build_population_cell(
            m_star_msun=c["m_star"], feh=c["feh"], n_systems=c["n"], seed=c["seed"],
            calibration=calibration, host_share=c["hosts"], planets_per_star=c["per_star"],
            systems_with_count=c["counts"], a_ice_au=c["a_ice"], systems_file=f"planets/{name}",
            flags=failed))
    out = WEB_PLANETS / "population.json"
    export.write_document(export.build_document(meta, population=export.build_population(
        star_masses_msun=PLANET_MASSES, feh_values=PLANET_FEHS,
        calibration_mass_msun=CALIBRATED_MSUN, calibration_feh=CALIBRATED_FEH, cells=cells,
        conclusions=planet_conclusions())), out)
    return out


PLANET_EXPERIMENTS = {"planet-grid": planet_grid, "planet-sensitivity": planet_sensitivity,
                      "planet-surveys": planet_surveys}


# ---- Figures --------------------------------------------------------------------------------

def figure(experiment: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, LogNorm

    panels = experiment["panels"]
    fig, axes = plt.subplots(len(panels), 1, figsize=(10, 4.2 * len(panels)), squeeze=False)
    for ax, pn in zip(axes[:, 0], panels):
        ax.set_title(pn["title"])
        ax.set_xlabel(pn["x_label"])
        ax.set_ylabel(pn["y_label"])
        rows = pn["rows"]
        if pn["kind"] == "heatmap":
            x, y = np.array(pn["x_values"]), np.array([r["y"] for r in rows])
            if any(lab in REMNANT_ORDER for r in rows for lab in r["labels"]):
                codes = np.array([[REMNANT_ORDER.index(lab) for lab in r["labels"]] for r in rows])
                cmap = ListedColormap(["#e8e4d8", "#5b8def", "#222222", "#d94f3d", "#9ccf8a",
                                       "#bbbbbb"])
                mesh = ax.pcolormesh(x, y, codes, cmap=cmap, vmin=-0.5, vmax=5.5, shading="nearest")
                bar = fig.colorbar(mesh, ax=ax, ticks=range(6))
                bar.ax.set_yticklabels(REMNANT_ORDER)
            else:
                z = np.array([[np.nan if v is None else v for v in r["values"]] for r in rows])
                mesh = ax.pcolormesh(x, y, z, shading="nearest",
                                     norm=LogNorm() if pn["log_values"] else None)
                fig.colorbar(mesh, ax=ax, label=pn["value_label"])
            ax.set_xscale("log" if pn["log_x"] else "linear")
        elif pn["kind"] == "curves":
            for r in rows:
                ax.plot(pn["x_values"], [np.nan if v is None else v for v in r["values"]],
                        label=r["label"])
            ax.set_xscale("log" if pn["log_x"] else "linear")
            ax.set_yscale("log" if pn["log_values"] else "linear")
            ax.legend(fontsize=7)
        else:
            ax.axis("off")
            text = [[lab if lab is not None else ("—" if v is None else f"{v:.4g}")
                     for v, lab in zip(r["values"], r["labels"])] for r in rows]
            ax.table(cellText=text, rowLabels=[r["label"] for r in rows],
                     colLabels=pn["columns"], loc="center").scale(1, 1.6)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---- Running --------------------------------------------------------------------------------

def planet_meta() -> dict:
    return export.build_meta(
        dataset="none: a semi-analytic model, no observational data enters the predictions",
        models={"planets": "Ida, Lin & Nagasawa 2013 gas phase (core growth, disk-limited gas "
                           "accretion with gap taper, type I with C1, type II from the viscous "
                           "gap mass); 15 seeds per disk plus next-generation seeds (Ida & Lin "
                           "2008a, 2010); resonant convoys and giant impacts after the gas to "
                           "1 Gyr (Ida & Lin 2010; 2004a eq. 24)",
                "disks": "f_g,0 log-normal (1 dex) centred on M★ (disk mass roughly linear in M★, "
                         "Andrews et al. 2013), kept within 0.1-10 times the centre (Ida, Lin & "
                         "Nagasawa 2013); f_d,0 = f_g,0 10^[Fe/H]; τ_disk log-uniform 1-10 Myr",
                "classes": "ordered rules on mass, envelope fraction and core ice",
                "radius": "Chen & Kipping 2017 mean mass-radius relation, for display"},
        inputs={"systems_per_cell": float(PLANET_SYSTEMS), "seed": float(PLANET_SEED),
                "c1": planet_population.C1_DEFAULT, "alpha": planet_population.ALPHA_DEFAULT,
                "f_g_sigma_dex": planet_population.F_G_SIGMA_DEX,
                "tau_disk_min_yr": planet_population.TAU_DISK_RANGE_YR[0],
                "tau_disk_max_yr": planet_population.TAU_DISK_RANGE_YR[1],
                "steps_per_dex": float(planet_population.STEPS_PER_DEX),
                "m_min_planet_mearth": planet_population.M_MIN_PLANET},
        reference_keys=["IdaLin2004a", "IdaLin2004b", "IdaLin2005", "IdaLin2008a",
                        "IdaLin2010", "IdaLinNagasawa2013", "Hayashi1981", "KokuboIda1998", "Ikoma2000", "Andrews2013",
                        "ChenKipping2017", "OwenWu2017"],
        seed=PLANET_SEED, created=export.git_commit_time())


def result_document(name: str, params: dict) -> dict:
    if name in PLANET_EXPERIMENTS:
        meta = planet_meta()
        return export.build_document(meta, experiment=PLANET_EXPERIMENTS[name](params))
    if name in STRUCTURE_EXPERIMENTS:
        meta = export.build_meta(
            dataset="MIST v1.2 zero-age stars (EEP 202) for comparison; OPAL and Ferguson et al. "
                    "2005 opacity tables for the Asplund et al. 2009 mixture, from MESA",
            models={"structure": "four structure equations fitted at half the mass, milestone 5: "
                                 "tabulated opacity, pp and CNO, Saha ionisation of H and He, "
                                 "mixing length 1.82"},
            inputs={"masses": float(len(EXTENSION_MASSES)), "feh_count": float(len(EXTENSION_FEHS))},
            reference_keys=["Choi2016", "Kippenhahn2012", "IglesiasRogers1996", "Asplund2009"],
            created=export.git_commit_time())
        return export.build_document(meta, experiment=STRUCTURE_EXPERIMENTS[name](params))
    meta = export.build_meta(
        dataset=export.DATASET,
        models={"track": "MIST v1.2 EEP tracks, bilinear EEP interpolation in log mass and [Fe/H]",
                "remnant": "fryer2012-delayed (alternative fryer2012-rapid); "
                           "belczynski2016-m10 pair instability",
                "imf": "kroupa2001, 0.1-100 M☉"},
        inputs={k: float(v) for k, v in params.items() if k != "feh"}
        | dict(zip(("feh_from", "feh_to", "feh_step"), feh_grid_spec(params["feh"]))),
        reference_keys=REFERENCES, seed=params["seed"], created=export.git_commit_time())
    return export.build_document(meta, experiment=EXPERIMENTS[name](params))


def feh_grid_spec(spec: str) -> tuple[float, float, float]:
    return tuple(float(x) for x in spec.split(":"))


def _machine() -> dict:
    cpu = next((ln.split(":", 1)[1].strip() for ln in Path("/proc/cpuinfo").read_text().splitlines()
                if ln.startswith("model name")), platform.processor()) \
        if Path("/proc/cpuinfo").exists() else platform.processor()
    return {"cpu": cpu, "cpus": os.cpu_count(), "python": platform.python_version(),
            "numpy": np.__version__}


def run(name: str, params: dict, export_web: bool = False) -> Path:
    start, started = time.perf_counter(), datetime.now(UTC)
    document = result_document(name, params)
    out = RESULTS / name / started.strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True)
    text = json.dumps(document, separators=(",", ":"), ensure_ascii=False) + "\n"
    (out / "result.json").write_text(text)
    figure(document["experiment"], out / "figure.png")
    (out / "run.json").write_text(json.dumps({
        "command": ["python", "-m", "stellarforge.experiments", *sys.argv[1:]],
        "experiment": name, "parameters": params,
        "git_commit": document["meta"]["generator"]["git_commit"],
        "uncommitted_changes": export.code_changed(), "mist_version": "1.2",
        "started": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds": round(time.perf_counter() - start, 2), "machine": _machine(),
    }, indent=1) + "\n")
    if export_web:
        WEB_EXPERIMENTS.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out / "result.json", WEB_EXPERIMENTS / f"{name}.json")
    return out


def parse(argv: list[str]) -> tuple[list[str], dict, bool]:
    if not argv or argv[0] not in (*EXPERIMENTS, *STRUCTURE_EXPERIMENTS, *PLANET_EXPERIMENTS,
                                   "all", "planets"):
        raise SystemExit(__doc__)
    params, export_web = dict(DEFAULTS), False
    for arg in argv[1:]:
        key, _, value = arg.removeprefix("--").partition("=")
        if key == "export" and not value:
            export_web = True
        elif key in params and value:
            params[key] = value if key == "feh" else int(value)
        else:
            raise SystemExit(f"unknown option {arg!r}\n{__doc__}")
    feh_grid(params["feh"])  # fails early on a malformed range
    names = {"all": list(EXPERIMENTS), "planets": list(PLANET_EXPERIMENTS)}.get(argv[0], [argv[0]])
    return names, params, export_web


def main(argv: list[str]) -> None:
    names, params, export_web = parse(argv)
    for name in names:
        start = time.perf_counter()
        out = run(name, params, export_web)
        print(f"{name}: {out.relative_to(ROOT)} ({time.perf_counter() - start:.1f} s)", flush=True)
    if export_web and "planet-grid" in names:
        print(f"planets: {export_planets(planet_meta()).relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
