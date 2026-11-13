"""Reads MIST EEP track archives (Choi et al. 2016; Dotter 2016) in place, without unpacking.

Run: .venv/bin/python -m stellarforge.mist inventory [archive.txz ...]
     (default: every archive in ~/.cache/stellar-forge/mist/; writes
      documentation/data/MIST coverage.md)
     .venv/bin/python -m stellarforge.mist convert [archive.txz ...]
     (writes one float32 .npz per metallicity to ~/.cache/stellar-forge/grids/)
"""

import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

CACHE = Path.home() / ".cache" / "stellar-forge" / "mist"
GRIDS = CACHE.parent / "grids"
REPORT = Path(__file__).parent.parent / "documentation" / "data" / "MIST coverage.md"

# Contract name -> column name, per MIST version, so no version is hard-wired. The .eep headers
# carry no units; the units in the names follow MESA's conventions as documented by Choi et al. 2016.
COLUMNS = {
    "1.2": {
        "age_yr": "star_age",
        "mass_msun": "star_mass",
        "log_l_lsun": "log_L",
        "log_teff_k": "log_Teff",
        "log_r_rsun": "log_R",
        "log_g_cgs": "log_g",
        "he_core_mass_msun": "he_core_mass",
        "c_core_mass_msun": "c_core_mass",
        "o_core_mass_msun": "o_core_mass",
        "center_h1": "center_h1",
        "center_he4": "center_he4",
        "log_center_t_k": "log_center_T",
        "log_center_rho_cgs": "log_center_Rho",
        "phase": "phase",
    },
}
# v2.5 keeps v1.2's names for every kept column; the inventory's "missing here" line checks this.
COLUMNS["2.5"] = COLUMNS["1.2"]

# MIST primary EEP numbers and the evolutionary point each marks, per version (v1.2: Dotter 2016,
# table 1). For "high-mass" tracks EEP 808 marks the end of core carbon burning instead (see
# Track.ending). The headers list these numbers directly, since a file's row n is EEP n.
PRIMARY_EEPS = {
    "1.2": {
        1: "pre-main sequence", 202: "zero-age main sequence",
        353: "intermediate-age main sequence", 454: "end of main sequence",
        605: "tip of red giant branch", 631: "zero-age core helium burning",
        707: "end of core helium burning", 808: "start of thermally pulsing AGB",
        1409: "post-AGB", 1710: "white-dwarf cooling sequence",
    },
}
# shortcut: v2.5's EEP definitions (Dotter et al. 2026, in press) are not yet checked; 1420 is
# unnamed and 1721 is assumed to be the white-dwarf point because it ends the longest tracks, as
# 1710 does in v1.2. Replace both once the paper is read.
PRIMARY_EEPS["2.5"] = {**PRIMARY_EEPS["1.2"], 1420: "EEP 1420 (v2.5, definition not yet checked)",
                       1721: "white-dwarf cooling sequence (assumed for v2.5)"}
del PRIMARY_EEPS["2.5"][1710]


# MIST's `phase` column (Choi et al. 2016, section 5.1 and the MIST track README). MIST reuses the
# numbers on tracks it labels `high-mass`, where 2 only means "end of the main sequence to helium
# ignition" (Choi et al. 2016, fig. 12) and no AGB exists, so those tracks get their own names.
PHASE_NAMES = {-1: "pre-main sequence", 0: "main sequence", 2: "red giant branch",
               3: "core helium burning", 4: "early AGB", 5: "thermally pulsing AGB",
               6: "post-AGB and white dwarf", 9: "Wolf–Rayet"}
PHASE_NAMES_HIGH_MASS = {**PHASE_NAMES, 2: "end of main sequence to helium ignition",
                         4: "after core helium burning", 5: "end of core carbon burning"}


def phase_names(star_type: str) -> dict[int, str]:
    return PHASE_NAMES_HIGH_MASS if star_type == "high-mass" else PHASE_NAMES


@dataclass
class Track:
    initial_mass_msun: float
    feh: float
    zinit: float
    yinit: float
    vvcrit: float
    version: str
    n_pts: int
    n_rows: int
    eeps: list[int]
    star_type: str
    columns: list[str]
    final_age_yr: float
    final_phase: float
    # Kept columns (COLUMNS order), one row per EEP from EEP 1; NaN where a column is absent.
    data: np.ndarray = field(default=None, repr=False)

    @property
    def last_primary_eep(self) -> int:
        """The highest primary EEP the track reaches."""
        return self.eeps[-1]

    @property
    def ending(self) -> str:
        if self.last_primary_eep == 808 and self.star_type == "high-mass":
            return "end of core carbon burning"
        names = PRIMARY_EEPS[self.version]
        return names.get(self.last_primary_eep, f"EEP {self.last_primary_eep} (not a known primary EEP)")


def _numbers(line: str) -> list[str]:
    return line.lstrip("#").split()


def parse_eep(text: str) -> Track:
    """Parses one .track.eep file: header values, column names and the final row."""
    lines = text.splitlines()
    header = [ln for ln in lines if ln.startswith("#")]
    rows = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    if len(header) < 12 or not rows:
        raise ValueError("not a MIST .track.eep file: header or data missing")
    version = header[0].split("=")[1].strip()
    yinit, zinit, feh, _afe, vvcrit = (float(x) for x in _numbers(header[4]))
    mass, n_pts, _n_eep, n_col, _phase, star_type = _numbers(header[7])
    eeps = [int(x) for x in _numbers(header[8])[1:]]
    columns = _numbers(header[11])
    if len(columns) != int(n_col):
        raise ValueError(f"header says {n_col} columns, found {len(columns)} names")
    names = list(COLUMNS[version].values())
    present = [columns.index(c) for c in names if c in columns]
    table = np.loadtxt(rows, usecols=present, ndmin=2)
    data = np.full((len(rows), len(names)), np.nan)
    data[:, [i for i, c in enumerate(names) if c in columns]] = table
    last = rows[-1].split()
    return Track(
        initial_mass_msun=float(mass), feh=feh, zinit=zinit, yinit=yinit, vvcrit=vvcrit,
        version=version, n_pts=int(n_pts), n_rows=len(rows), eeps=eeps, star_type=star_type,
        columns=columns, final_age_yr=float(last[columns.index("star_age")]),
        final_phase=float(last[columns.index("phase")]), data=data,
    )


def read_archive(path: Path):
    """Yields every track in a MIST .txz, streamed: the archive is never unpacked to disk."""
    with tarfile.open(path, "r|xz") as tar:
        for member in tar:
            if member.isfile() and member.name.endswith(".track.eep"):
                yield parse_eep(tar.extractfile(member).read().decode("ascii"))


def _mass_list(masses: list[float]) -> str:
    return ", ".join(f"{m:g}" for m in masses)


def inventory_section(name: str, tracks: list[Track]) -> str:
    tracks = sorted(tracks, key=lambda t: t.initial_mass_msun)
    t0 = tracks[0]
    missing = sorted(set(COLUMNS[t0.version].values()) - set(t0.columns))
    bad_rows = [t.initial_mass_msun for t in tracks if t.n_rows != t.n_pts]
    out = [
        f"## [Fe/H] = {t0.feh:+.2f}",
        "",
        (f"`{name}`: MIST v{t0.version}, Z_init = {t0.zinit:.5g}, Y_init = {t0.yinit:.4g}, "
        f"v/vcrit = {t0.vvcrit:g}, [α/Fe] = 0."),
        "",
        (f"- **Tracks:** {len(tracks)}, from {t0.initial_mass_msun:g} to "
        f"{tracks[-1].initial_mass_msun:g} M☉"),
        f"- **Points per track:** {min(t.n_pts for t in tracks)} to {max(t.n_pts for t in tracks)}",
        (f"- **Row counts match the header:** "
        f"{'yes' if not bad_rows else 'no, for ' + _mass_list(bad_rows)}"),
        f"- **Columns kept by `mist.py` missing here:** {', '.join(missing) or 'none'}",
        "",
        "| Last primary EEP reached | Final MIST phase | Tracks | Masses (M☉) |",
        "| --- | --- | --- | --- |",
    ]
    by_end: dict[tuple[int, str, float], list[float]] = {}
    for t in tracks:
        by_end.setdefault((t.last_primary_eep, t.ending, t.final_phase), []).append(
            t.initial_mass_msun)
    for (eep, ending, phase), masses in sorted(by_end.items()):
        out.append(f"| {eep}: {ending} | {phase:g} | {len(masses)} | {_mass_list(masses)} |")
    return "\n".join(out) + "\n"


def inventory(archives: list[Path]) -> str:
    sections, columns = [], None
    for path in archives:
        tracks = list(read_archive(path))
        if not tracks:
            raise ValueError(f"{path} holds no .track.eep files")
        sections.append((tracks[0].feh, inventory_section(path.name, tracks)))
        columns = columns or (tracks[0].version, tracks[0].columns)
    version, names = columns
    mapped = {v: k for k, v in COLUMNS[version].items()}
    col_rows = [f"| {i} | `{c}` | {'`' + mapped[c] + '`' if c in mapped else ''} |"
                for i, c in enumerate(names, 1)]
    return "\n".join([
        "# MIST coverage",
        "",
        ("Written by `python -m stellarforge.mist inventory` from the archives in "
        "`~/.cache/stellar-forge/mist/`; do not edit by hand. Source: MIST v1.2 EEP tracks "
        "(Choi et al. 2016; Dotter 2016), https://mist.science."),
        "",
        ("A track's ending is the last primary EEP it reaches (Dotter 2016, table 1). EEP 808 is "
        "the start of the thermally pulsing AGB on tracks MIST labels `low-mass` and the end of "
        "core carbon burning on tracks it labels `high-mass`. MIST phases: "
        + ", ".join(f"{k} {v}" for k, v in PHASE_NAMES.items())
        + "; on `high-mass` tracks, "
        + ", ".join(f"{k} {v}" for k, v in PHASE_NAMES_HIGH_MASS.items() if v != PHASE_NAMES[k])
        + "."),
        "",
        *[s for _, s in sorted(sections)],
        "## Columns",
        "",
        (f"MIST v{version} .eep files have {len(names)} columns. The header gives names only, no "
        "units; the units in the contract names follow MESA's conventions (Choi et al. 2016). "
        "The right-hand column shows the contract name for each column `mist.py` keeps."),
        "",
        "| # | MIST name | Kept as |",
        "| --- | --- | --- |",
        *col_rows,
        "",
    ])


def convert(archive: Path, out_dir: Path = GRIDS) -> Path:
    """One metallicity's tracks as a compact float32 grid, `data[track, eep - 1, column]`, plus
    `age_yr[track, eep - 1]` in float64."""
    tracks = sorted(read_archive(archive), key=lambda t: t.initial_mass_msun)
    if not tracks:
        raise ValueError(f"{archive} holds no .track.eep files")
    t0 = tracks[0]
    data = np.full((len(tracks), max(t.n_rows for t in tracks), len(COLUMNS[t0.version])), np.nan,
                   dtype=np.float32)
    # Ages stay float64: float32 steps (~500 yr at 5 Gyr) are longer than late phases' EEP spacing.
    age = np.full(data.shape[:2], np.nan)
    for i, t in enumerate(tracks):
        data[i, :t.n_rows] = t.data
        age[i, :t.n_rows] = t.data[:, 0]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / archive.name.replace(".txz", ".npz")
    # Written beside the target and renamed, so a killed run never leaves a broken grid file
    # (a file handle, so numpy adds no .npz and load_grid's glob never picks up the partial file)
    tmp = out.with_name(out.name + ".part")
    with tmp.open("wb") as fh:
        np.savez_compressed(
            fh, data=data, age_yr=age, columns=np.array(list(COLUMNS[t0.version])),
            masses_msun=np.array([t.initial_mass_msun for t in tracks]),
            n_rows=np.array([t.n_rows for t in tracks]),
            last_primary_eep=np.array([t.last_primary_eep for t in tracks]),
            ending=np.array([t.ending for t in tracks]),
            star_type=np.array([t.star_type for t in tracks]),
            feh=t0.feh, zinit=t0.zinit, yinit=t0.yinit, vvcrit=t0.vvcrit, version=t0.version,
        )
    tmp.replace(out)
    return out


def main(argv: list[str]) -> None:
    if not argv or argv[0] not in ("inventory", "convert"):
        raise SystemExit(__doc__)
    archives = [Path(a) for a in argv[1:]] or sorted(CACHE.glob("MIST_v1.2_*.txz"))
    if not archives:
        raise SystemExit(f"no archives in {CACHE}; run scripts/fetch_mist.py first")
    if argv[0] == "convert":
        for archive in archives:
            start = time.perf_counter()
            out = convert(archive)
            print(f"{out}: {time.perf_counter() - start:.1f} s, {out.stat().st_size / 1e6:.1f} MB")
        return
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(inventory(archives))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main(sys.argv[1:])
