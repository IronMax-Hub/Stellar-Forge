"""Experiments across mass and metallicity: lifetimes, remnants and an IMF population (Phase 3).

Run: .venv/bin/python -m stellarforge.experiments <experiment> [options]
     experiments: lifetime-map, full-life-map, remnant-map, remnant-mass-curves, population,
                  sun-metallicities, all
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

from . import evolution, export, remnants
from .colour import temperature_to_rgb

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

def result_document(name: str, params: dict) -> dict:
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
    if not argv or argv[0] not in (*EXPERIMENTS, "all"):
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
    names = list(EXPERIMENTS) if argv[0] == "all" else [argv[0]]
    return names, params, export_web


def main(argv: list[str]) -> None:
    names, params, export_web = parse(argv)
    for name in names:
        start = time.perf_counter()
        out = run(name, params, export_web)
        print(f"{name}: {out.relative_to(ROOT)} ({time.perf_counter() - start:.1f} s)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
