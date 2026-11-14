"""A star's track for any mass and [Fe/H] inside the MIST v1.2 grid (Choi et al. 2016; Dotter 2016).

Tracks are blended at equal EEP (equivalent evolutionary phase), bilinearly in log mass and [Fe/H],
only when all four corner tracks of the grid cell end at the same primary EEP. Otherwise the
nearest corner track is used, labelled substituted, with a flag. Nothing outside the grid is extrapolated.

Run: .venv/bin/python -m stellarforge.evolution check
     (leave-one-out interpolation errors; writes documentation/data/MIST interpolation check.md)
"""

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from .mist import CACHE, GRIDS, PRIMARY_EEPS, phase_names, read_archive

REPORT = Path(__file__).parent.parent / "documentation" / "data" / "MIST interpolation check.md"

# Endings after which nothing more happens to the star in MIST, and the one it has not reached yet.
FINAL_ENDINGS = ("white-dwarf cooling sequence", "end of core carbon burning")
MS_END = "end of main sequence"
CARBON_END = "end of core carbon burning"
# Many MIST v1.2 tracks reach the end of carbon burning with a helium-free centre but report a
# zero CO-core (or helium-core) mass; such endings are kept apart, so they never blend with tracks
# whose core masses are known (their remnants need those masses).
NO_CO_CORE = CARBON_END + ", CO-core mass missing in MIST"
NO_HE_CORE = CARBON_END + ", helium-core mass missing in MIST"
UNIVERSE_AGE_YR = 13.8e9
INTERPOLATION_TARGET_DEX = 0.02    # build plan, Validation: main-sequence log L and log Teff


@dataclass(frozen=True)
class Grid:
    fehs: np.ndarray          # (F,) sorted
    masses_msun: np.ndarray   # (M,) sorted, the same at every [Fe/H]
    columns: tuple[str, ...]
    data: tuple[np.ndarray, ...]     # per [Fe/H]: (M, max rows, columns) float32, NaN-padded
    age_yr: tuple[np.ndarray, ...]   # per [Fe/H]: (M, max rows) float64, replaces data's age column
    n_rows: np.ndarray        # (F, M)
    ending: np.ndarray        # (F, M) str
    star_type: np.ndarray     # (F, M) str: MIST's `low-mass` or `high-mass` label
    version: str

    def rows(self, i_feh: int, i_mass: int) -> np.ndarray:
        n = self.n_rows[i_feh, i_mass]
        rows = self.data[i_feh][i_mass, :n].astype(np.float64)
        rows[:, self.columns.index("age_yr")] = self.age_yr[i_feh][i_mass, :n]
        return rows


def _read_npz(path: Path) -> dict[str, np.ndarray]:
    """Every array read once, and the file closed."""
    with np.load(path) as z:
        return dict(z)


@lru_cache(maxsize=1)
def load_grid(directory: Path = GRIDS) -> Grid:
    files = sorted(directory.glob("MIST_v1.2_*.npz"))
    if not files:
        raise FileNotFoundError(f"no converted grids in {directory}; run `make data`")
    parts = sorted((_read_npz(f) for f in files), key=lambda z: float(z["feh"]))
    masses = parts[0]["masses_msun"]
    if any(not np.array_equal(p["masses_msun"], masses) for p in parts):
        raise ValueError("the MIST mass grid differs between metallicities")
    columns = [str(c) for c in parts[0]["columns"]]
    he, co = columns.index("he_core_mass_msun"), columns.index("c_core_mass_msun")
    for p in parts:
        last = p["data"][np.arange(len(masses)), p["n_rows"] - 1]
        carbon = p["ending"] == CARBON_END
        p["ending"] = np.where(carbon & (last[:, co] <= 0), NO_CO_CORE, p["ending"])
        p["ending"] = np.where(carbon & (last[:, he] <= 0), NO_HE_CORE, p["ending"])
    return Grid(
        fehs=np.array([float(p["feh"]) for p in parts]), masses_msun=masses,
        columns=tuple(str(c) for c in parts[0]["columns"]), data=tuple(p["data"] for p in parts),
        age_yr=tuple(p["age_yr"] for p in parts),
        n_rows=np.array([p["n_rows"] for p in parts]),
        ending=np.array([p["ending"] for p in parts]),
        star_type=np.array([p["star_type"] for p in parts]), version=str(parts[0]["version"]),
    )


def _bracket(axis: np.ndarray, x: float, name: str) -> list[tuple[int, float]]:
    """Grid indices and linear weights around x; one index when x is a grid value."""
    if not axis[0] <= x <= axis[-1]:
        raise ValueError(f"{name} {x:g} is outside the MIST grid ({axis[0]:g} to {axis[-1]:g}); "
                         "no extrapolation")
    hit = np.flatnonzero(np.isclose(axis, x, rtol=0, atol=1e-9))
    if hit.size:
        return [(int(hit[0]), 1.0)]
    hi = int(np.searchsorted(axis, x))
    w = (x - axis[hi - 1]) / (axis[hi] - axis[hi - 1])
    return [(hi - 1, 1 - w), (hi, w)]


@dataclass
class Track:
    mass_msun: float
    feh: float
    method: str
    provenance: str          # published (a MIST track), interpolated, or substituted (nearest track)
    ending: str
    star_type: str           # MIST's label for the track whose phases are used
    flags: list[str]
    values: dict[str, np.ndarray]   # MIST column (contract name) -> one value per EEP from EEP 1

    @property
    def phase_names(self) -> dict[int, str]:
        return phase_names(self.star_type)

    @property
    def primary_eep_rows(self) -> list[int]:
        """Row indices of the primary EEPs this track reaches."""
        n = len(self.values["age_yr"])
        return [e - 1 for e in PRIMARY_EEPS["1.2"] if e <= n]


def _ending_flags(ending: str) -> list[str]:
    if ending in FINAL_ENDINGS:
        return []
    if ending.startswith(CARBON_END):
        return ["core_mass_missing_in_mist"]
    if ending == MS_END:
        return ["still_on_main_sequence_at_track_end"]
    return [f"track_incomplete: stops at {ending}"]


_OVER_TARGET: dict[int, set[tuple[int, int]]] = {}


def _over_target(grid: Grid) -> set[tuple[int, int]]:
    """Grid points (i_feh, i_mass) that, rebuilt from their neighbours along either axis
    (`leave_one_out`), miss INTERPOLATION_TARGET_DEX in log L or log Teff on the main sequence."""
    if id(grid) not in _OVER_TARGET:
        i_mass = {float(m): i for i, m in enumerate(grid.masses_msun)}
        i_feh = {float(f): i for i, f in enumerate(grid.fehs)}
        _OVER_TARGET[id(grid)] = {(i_feh[r[1]], i_mass[r[0]])
                                  for rows in leave_one_out(grid).values() for r in rows
                                  if max(r[2], r[3]) > INTERPOLATION_TARGET_DEX}
    return _OVER_TARGET[id(grid)]


def _blend_flags(grid: Grid, corners: list[tuple[int, int, float]]) -> list[str]:
    """Warnings for a star built from more than one grid track."""
    flags = []
    if any(f in (0, len(grid.fehs) - 1) or m in (0, len(grid.masses_msun) - 1)
           for f, m, _ in corners):
        flags.append("near_grid_boundary")
    if any((f, m) in _over_target(grid) for f, m, _ in corners):
        flags.append(f"interpolation_error_may_exceed_{INTERPOLATION_TARGET_DEX:g}_dex: a corner "
                     "track rebuilt from its neighbours misses log L or log Teff by more on the "
                     "main sequence")
    return flags


def build_track(mass_msun: float, feh: float, grid: Grid | None = None) -> Track:
    grid = grid or load_grid()
    ms = _bracket(np.log10(grid.masses_msun), float(np.log10(mass_msun)), "log mass")
    fs = _bracket(grid.fehs, feh, "[Fe/H]")
    corners = [(f, m, wf * wm) for f, wf in fs for m, wm in ms if wf * wm > 0]
    endings = {str(grid.ending[f, m]) for f, m, _ in corners}
    near_f, near_m, _ = max(corners, key=lambda c: c[2])
    ending = str(grid.ending[near_f, near_m])
    star_type = str(grid.star_type[near_f, near_m])

    if len(corners) == 1 or len(endings) > 1:
        rows = grid.rows(near_f, near_m)
        exact = len(corners) == 1
        d_logm = abs(np.log10(mass_msun / grid.masses_msun[near_m]))
        method = ("MIST grid track" if exact else
                  f"nearest MIST track: {grid.masses_msun[near_m]:g} M☉, "
                  f"[Fe/H] {grid.fehs[near_f]:+.2f}; {d_logm:.3f} dex away in log mass, "
                  f"{abs(feh - grid.fehs[near_f]):.2f} in [Fe/H]")
        flags = [] if exact else ["nearest_track_used", "cell_tracks_end_differently",
                                  *[f for f in _blend_flags(grid, corners)
                                    if f == "near_grid_boundary"]]   # nothing blended here
        return Track(mass_msun, feh, method, "published" if exact else "substituted", ending,
                     star_type,
                     flags + _ending_flags(ending), dict(zip(grid.columns, rows.T)))

    n = min(grid.n_rows[f, m] for f, m, _ in corners)
    rows = sum(w * grid.rows(f, m)[:n] for f, m, w in corners)
    values = dict(zip(grid.columns, rows.T))
    # A blended phase label means nothing; take the nearest corner's, with its star type.
    values["phase"] = grid.rows(near_f, near_m)[:n, grid.columns.index("phase")]
    return Track(mass_msun, feh, "EEP interpolation (log mass, [Fe/H])", "interpolated", ending,
                 star_type, _blend_flags(grid, corners) + _ending_flags(ending), values)


class Star:
    """One star of initial mass `mass_msun` and [Fe/H] `feh`, from the MIST v1.2 grid."""

    def __init__(self, mass_msun: float, feh: float, grid: Grid | None = None):
        self._track = build_track(mass_msun, feh, grid)

    def track(self) -> Track:
        return self._track

    def at(self, age_yr: float) -> dict[str, float]:
        """Every kept column at this age, linear in age between neighbouring EEPs."""
        v = self._track.values
        age = v["age_yr"]
        if not age[0] <= age_yr <= age[-1]:
            raise ValueError(f"age {age_yr:.4g} yr is outside this track "
                             f"({age[0]:.4g} to {age[-1]:.4g} yr)")
        out = {k: float(np.interp(age_yr, age, x)) for k, x in v.items() if k != "phase"}
        out["phase"] = float(v["phase"][np.searchsorted(age, age_yr, side="right") - 1])
        return out

    def phases(self) -> list[tuple[str, float, float]]:
        """(MIST phase name, start age, end age) for each run of one phase along the track."""
        v, names = self._track.values, self._track.phase_names
        phase, age = v["phase"], v["age_yr"]
        starts = [0, *np.flatnonzero(np.diff(phase)) + 1]
        ends = [*starts[1:], len(phase)]
        return [(names[int(phase[s])], float(age[s]), float(age[min(e, len(age) - 1)]))
                for s, e in zip(starts, ends)]


def _trios(grid: Grid, min_rows: int):
    """(axis, i_feh, i_mass, weight, trio) for each interior track and its two neighbours along
    mass (in log mass) or [Fe/H], when all three end alike and reach `min_rows` EEPs."""
    logm = np.log10(grid.masses_msun)
    for axis, positions in (("mass", logm), ("feh", grid.fehs)):
        for f in range(len(grid.fehs)):
            for m in range(len(logm)):
                i = m if axis == "mass" else f
                if not 0 < i < len(positions) - 1:
                    continue
                trio = [(f, j) if axis == "mass" else (j, m) for j in (i - 1, i, i + 1)]
                if len({str(grid.ending[c]) for c in trio}) > 1 or min(
                        grid.n_rows[c] for c in trio) < min_rows:
                    continue
                w = (positions[i] - positions[i - 1]) / (positions[i + 1] - positions[i - 1])
                yield axis, f, m, w, trio


def leave_one_out(grid: Grid) -> dict[str, list[tuple[float, float, float, float]]]:
    """Main-sequence errors (EEP 202-454) when each interior grid track is rebuilt from its two
    neighbours, along mass and along [Fe/H]. Only neighbours that end like the track are used.
    Returns axis -> [(mass, feh, max |d log L|, max |d log Teff|, the same two up to 13.8 Gyr)]."""
    ms = slice(201, 454)
    li, ti, ai = (grid.columns.index(c) for c in ("log_l_lsun", "log_teff_k", "age_yr"))
    out: dict[str, list] = {"mass": [], "feh": []}
    for axis, f, m, w, trio in _trios(grid, 454):
        guess = (1 - w) * grid.rows(*trio[0])[ms] + w * grid.rows(*trio[2])[ms]
        truth = grid.rows(*trio[1])[ms]
        err = np.abs(guess - truth)
        young = err[truth[:, ai] <= UNIVERSE_AGE_YR]
        young = young if len(young) else np.zeros_like(err[:1])
        out[axis].append((float(grid.masses_msun[m]), float(grid.fehs[f]),
                          float(err[:, li].max()), float(err[:, ti].max()),
                          float(young[:, li].max()), float(young[:, ti].max())))
    return out


# Compared at every EEP of a stage, in dex; the age is the age each EEP (phase point) is reached.
WIDE_QUANTITIES = (("log L", "log_l_lsun"), ("log Teff", "log_teff_k"), ("log R", "log_r_rsun"),
                   ("log age", "age_yr"))
# Compared at the last EEP of tracks that end finally (the remnant's inputs), as a fraction.
FINAL_QUANTITIES = (("final mass", "mass_msun"), ("final helium core", "he_core_mass_msun"),
                    ("final CO core", "c_core_mass_msun"))


def wide_check(grid: Grid) -> dict[tuple[str, str, str], list[float]]:
    """Each rebuilt track's largest error, by (axis, stage, quantity), from the same leave-one-out
    rebuilds as `leave_one_out`, over the main sequence, after it, and at the track's end."""
    out: dict[tuple[str, str, str], list[float]] = {}
    for axis, _f, _m, w, trio in _trios(grid, 454):
        n = min(grid.n_rows[c] for c in trio)
        lo, truth, hi = (grid.rows(*c)[:n] for c in trio)
        guess = (1 - w) * lo + w * hi
        stages = [("main sequence", slice(201, 454))]
        if n > 455:
            stages.append(("after the main sequence", slice(453, n)))
        for stage, rows in stages:
            for name, col in WIDE_QUANTITIES:
                j = grid.columns.index(col)
                g, t = guess[rows, j], truth[rows, j]
                if col == "age_yr":
                    g, t = np.log10(g), np.log10(t)
                out.setdefault((axis, stage, name), []).append(float(np.abs(g - t).max()))
        # Only trios of equal length: otherwise row n-1 is not the left-out track's final state
        if str(grid.ending[trio[1]]) in FINAL_ENDINGS and len({grid.n_rows[c] for c in trio}) == 1:
            for name, col in FINAL_QUANTITIES:
                j = grid.columns.index(col)
                if min(lo[-1, j], truth[-1, j], hi[-1, j]) > 0:
                    out.setdefault((axis, "end of the track", name), []).append(
                        float(abs(guess[-1, j] / truth[-1, j] - 1)))
    return out


def float32_error(archive: Path, directory: Path = GRIDS) -> dict[str, tuple[float, float]]:
    """Column -> (largest absolute, largest relative) difference between one converted grid file
    and the float64 values streamed from its MIST archive."""
    grid = load_grid(directory)
    tracks = list(read_archive(archive))
    f = int(np.flatnonzero(np.isclose(grid.fehs, tracks[0].feh))[0])
    index = {float(m): i for i, m in enumerate(grid.masses_msun)}
    worst = np.zeros((2, len(grid.columns)))
    for t in tracks:
        stored = grid.rows(f, index[t.initial_mass_msun])
        err = np.abs(stored - t.data)
        with np.errstate(divide="ignore", invalid="ignore"):
            # Below ~1e-30 float32 stores 0 (underflow): a 100% relative error that means nothing
            rel = np.where(np.abs(t.data) > 1e-30, err / np.abs(t.data), 0.0)
        worst = np.fmax(worst, [np.nanmax(err, axis=0), np.nanmax(rel, axis=0)])
    return {c: (float(a), float(r)) for c, a, r in zip(grid.columns, *worst)}


def loo_report(grid: Grid, archive: Path | None = None) -> str:
    lines = [
        "# MIST interpolation check",
        "",
        ("Written by `python -m stellarforge.evolution check`; do not edit by hand. Each interior "
         "MIST v1.2 track is rebuilt from its two neighbours (along mass in log mass, or along "
         "[Fe/H]) at equal EEP, and compared on the main sequence (EEP 202–454). Only trios "
         "whose tracks end at the same primary EEP are used, as in `evolution.py`. Leaving a track "
         "out doubles the grid step, so these errors overstate those of the real interpolation."),
        "",
        "Target (build plan, Validation): main-sequence errors under 0.02 dex in log L and log Teff.",
        "Each track's error is its largest along the main sequence; the tables give the spread of",
        "those over all tracks, for the whole main sequence and for the part up to 13.8 Gyr (the",
        "lowest masses end their main sequence long after that).",
        "",
        ("| Axis | Part of the main sequence | Tracks | log L: median | 95th percentile | worst | "
         "log Teff: median | 95th percentile | worst | Tracks over 0.02 dex |"),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    results = leave_one_out(grid)
    for axis, rows in results.items():
        for part, cols in (("all of it", slice(2, 4)), ("up to 13.8 Gyr", slice(4, 6))):
            a = np.array([r[cols] for r in rows])
            over = int(np.sum(a.max(axis=1) > 0.02))
            lines.append(f"| {axis} | {part} | {len(rows)} | {np.median(a[:, 0]):.4f} | "
                         f"{np.percentile(a[:, 0], 95):.4f} | {a[:, 0].max():.4f} | "
                         f"{np.median(a[:, 1]):.4f} | {np.percentile(a[:, 1], 95):.4f} | "
                         f"{a[:, 1].max():.4f} | {over} |")
    for axis, rows in results.items():
        worst = sorted(rows, key=lambda r: -max(r[4:]))[:10]
        lines += ["", f"Worst ten along {axis}, up to 13.8 Gyr:", "",
                  "| Mass (M☉) | [Fe/H] | log L error | log Teff error |", "| --- | --- | --- | --- |",
                  *[f"| {r[0]:g} | {r[1]:+.2f} | {r[4]:.4f} | {r[5]:.4f} |" for r in worst]]
    lines += [
        "", "## Every stage and more quantities", "",
        ("The same rebuilds, compared over the main sequence (EEP 202–454) and after it (EEP 454 to "
         "the last EEP all three tracks reach), in dex; `log age` is the age at which each EEP, "
         "and so each phase, is reached. At the end of tracks that end finally (white dwarf or end "
         "of carbon burning), the final mass and core masses that the remnant rules use are "
         "compared as a fraction; trios where MIST gives no core mass are left out."),
        "",
        "| Axis | Stage | Quantity | Tracks | Median | 95th percentile | Worst |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for (axis, stage, name), errs in wide_check(grid).items():
        a = np.array(errs)
        fmt = "{:.1%}" if stage == "end of the track" else "{:.4f}"
        lines.append(f"| {axis} | {stage} | {name} | {len(a)} | " + " | ".join(
            fmt.format(x) for x in (np.median(a), np.percentile(a, 95), a.max())) + " |")
    if archive is not None:
        lines += [
            "", "## Storage precision", "",
            (f"`mist.py` stores every column but age as float32. Largest difference between the "
             f"stored grid and the float64 values streamed from `{archive.name}`:"),
            "", "| Column | Largest absolute difference | Largest relative difference |",
            "| --- | --- | --- |",
            *[f"| `{c}` | {a:.2g} | {r:.2g} |" for c, (a, r) in float32_error(archive).items()],
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> None:
    if argv != ["check"]:
        raise SystemExit(__doc__)
    archive = CACHE / "MIST_v1.2_feh_p0.00_afe_p0.0_vvcrit0.4_EEPS.txz"
    REPORT.write_text(loo_report(load_grid(), archive if archive.exists() else None))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main(sys.argv[1:])
