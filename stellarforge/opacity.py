"""Radiative opacities from the tables MIST v1.2 used (Choi et al. 2016, section 3.2.2).

- log T >= 3.75: OPAL Type I (Iglesias & Rogers 1996) for the Asplund et al. 2009 photospheric
  mixture, MESA's `a09_z*_x*.data`;
- log T <= 4.5: Ferguson et al. 2005 low-temperature tables for the same mixture,
  MESA's `lowT_fa05_a09p_z*_x*.data`.

Both come from MESA's `kap/kap_data.tar.xz` (MESAHub/mesa on GitHub, sha256 32d741f0...), which is
streamed once by `python -m stellarforge.opacity convert` into a small .npz in the cache; it is
never unpacked. Tables give log10 kappa (cm^2/g) on a grid of log T and log R, with
R = rho / T6^3 (rho in g/cm^3, T6 = T / 1e6 K), for 13 values of Z and 10 of X.
"""

import re
import sys
import tarfile
from pathlib import Path

import numpy as np
from scipy.interpolate import RectBivariateSpline

CACHE = Path.home() / ".cache" / "stellar-forge" / "mesa_kap"
ARCHIVE = CACHE / "kap_data.tar.xz"
TABLES = CACHE / "opacity_a09.npz"
ARCHIVE_SHA256 = "32d741f0ac9402faa76f056770ef2010364ec9f703bd745ca66da91f4eb8f145"
URL = "https://media.githubusercontent.com/media/MESAHub/mesa/main/kap/kap_data.tar.xz"
FAMILIES = {"opal": re.compile(r"kap_data/a09_z([0-9.]+)_x([0-9.]+)\.data$"),
            "lowt": re.compile(r"kap_data/lowT_fa05_a09p_z([0-9.]+)_x([0-9.]+)\.data$")}
# The tables overlap at log T 3.75-4.5; across this range the low-temperature table hands over to
# OPAL with a smooth (cosine) weight. shortcut: the blend edges are our choice, not MESA's
# documented defaults; check them against MESA's kap controls if the surface layers matter.
BLEND_LOG_T = (3.80, 4.00)


def parse_table(text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(log T, log R, log kappa[T, R]) from one MESA kap table."""
    lines = text.splitlines()
    head = lines.index(next(line for line in lines if line.strip().startswith("logT")))
    log_r = np.array(lines[head + 1].split(), dtype=float)
    rows = np.array([line.split() for line in lines[head + 2:] if line.strip()], dtype=float)
    if rows.shape[1] != len(log_r) + 1:
        raise ValueError(f"table rows have {rows.shape[1] - 1} values for {len(log_r)} log R columns")
    return rows[:, 0], log_r, rows[:, 1:]


def convert(archive: Path = ARCHIVE, out: Path = TABLES) -> Path:
    """Stream the archive once and keep the a09 tables, as arrays per family, in one .npz."""
    found: dict[str, dict[tuple[float, float], tuple]] = {k: {} for k in FAMILIES}
    with tarfile.open(archive, "r|xz") as tar:     # "r|": a single forward pass, nothing unpacked
        for member in tar:
            for family, pattern in FAMILIES.items():
                match = pattern.match(member.name)
                if match and member.isfile():
                    z, x = float(match[1]), float(match[2])
                    found[family][z, x] = parse_table(tar.extractfile(member).read().decode())
    arrays = {}
    for family, tables in found.items():
        zs = np.array(sorted({z for z, _ in tables}))
        xs = np.array(sorted({x for _, x in tables}))
        log_t, log_r, _ = next(iter(tables.values()))
        kappa = np.full((len(zs), len(xs), len(log_t), len(log_r)), np.nan)
        for (z, x), (t, r, k) in tables.items():
            if not (np.array_equal(t, log_t) and np.array_equal(r, log_r)):
                raise ValueError(f"{family} z={z} x={x}: grid differs from the others")
            kappa[np.searchsorted(zs, z), np.searchsorted(xs, x)] = k
        arrays |= {f"{family}_z": zs, f"{family}_x": xs, f"{family}_log_t": log_t,
                   f"{family}_log_r": log_r, f"{family}_log_kappa": kappa}
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **arrays)
    return out


def _bracket(values: np.ndarray, v: float, available: np.ndarray) -> list[tuple[int, float]]:
    """Indices and linear weights of the two grid values around v, among those with a table."""
    idx = np.flatnonzero(available)
    vals = values[idx]
    if not vals[0] <= v <= vals[-1]:
        raise ValueError(f"{v} is outside the tables' range {vals[0]}-{vals[-1]}")
    k = min(np.searchsorted(vals, v, side="right") - 1, len(vals) - 2)
    w = (v - vals[k]) / (vals[k + 1] - vals[k])
    return [(idx[k], 1 - w), (idx[k + 1], w)]


class Opacity:
    """kappa(rho, T) in SI for one uniform composition: the tables are interpolated linearly in Z
    and X (in log kappa), then by bicubic spline in log T and log R."""

    def __init__(self, x: float, z: float, tables: Path = TABLES):
        if not tables.exists():
            raise FileNotFoundError(f"{tables} is missing; run `make data`")
        data = np.load(tables)
        self.splines = {}
        for family in FAMILIES:
            kappa = data[f"{family}_log_kappa"]
            zs, xs = data[f"{family}_z"], data[f"{family}_x"]
            table = 0
            for i, wz in _bracket(zs, z, np.ones(len(zs), bool)):
                for j, wx in _bracket(xs, x, ~np.isnan(kappa[i, :, 0, 0])):
                    table = table + wz * wx * kappa[i, j]
            if np.isnan(table).any():
                raise ValueError(f"{family} tables have gaps at X={x}, Z={z}")
            log_t, log_r = data[f"{family}_log_t"], data[f"{family}_log_r"]
            self.splines[family] = (RectBivariateSpline(log_t, log_r, table), log_t, log_r)
        self.log_t_min = self.splines["lowt"][1][0]
        self.log_t_max = self.splines["opal"][1][-1]

    def _log_kappa(self, family: str, log_t: float, log_r: float) -> float:
        spline, ts, rs = self.splines[family]
        if not (ts[0] <= log_t <= ts[-1] and rs[0] <= log_r <= rs[-1]):
            raise ValueError(f"log T {log_t:.3f}, log R {log_r:.3f} is outside the {family} table")
        return float(spline(log_t, log_r)[0, 0])

    def __call__(self, rho, t):
        """kappa in m^2/kg for rho in kg/m^3 and T in K. Outside the tables it raises ValueError:
        no extrapolation."""
        log_t = np.log10(t)
        log_r = np.log10(rho * 1e-3) - 3 * (log_t - 6)
        lo, hi = BLEND_LOG_T
        if log_t <= lo:
            log_k = self._log_kappa("lowt", log_t, log_r)
        elif log_t >= hi:
            log_k = self._log_kappa("opal", log_t, log_r)
        else:
            w = 0.5 - 0.5 * np.cos(np.pi * (log_t - lo) / (hi - lo))   # 0 at lo, 1 at hi
            log_k = (1 - w) * self._log_kappa("lowt", log_t, log_r) \
                + w * self._log_kappa("opal", log_t, log_r)
        return 0.1 * 10**log_k


def main(argv: list[str]) -> None:
    if argv != ["convert"]:
        raise SystemExit("Run: .venv/bin/python -m stellarforge.opacity convert")
    print(convert())


if __name__ == "__main__":
    main(sys.argv[1:])
