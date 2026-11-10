"""Downloads MIST EEP track archives (v1.2: Choi et al. 2016; Dotter 2016) into the local cache.

Resumes a partial download and checks the final size against the server's. Archives are never
unpacked; stellarforge.mist reads them in place.

Run: .venv/bin/python scripts/fetch_mist.py p0.00            (one metallicity)
     .venv/bin/python scripts/fetch_mist.py all              (all 15)
     .venv/bin/python scripts/fetch_mist.py MIST_v2.5_feh_p000_afe_p0_vvcrit0.4_EEPS.txz
                                                     (any archive by its full name, v1.2 or v2.5)
"""

import sys
import urllib.request
from pathlib import Path

BASES = {"v1.2": "https://mist.science/data/tarballs_v1.2/",
         "v2.5": "https://mist.science/data/tarballs_v2.5/eeps/"}
CACHE = Path.home() / ".cache" / "stellar-forge" / "mist"
# The 15 [Fe/H] values MIST v1.2 publishes, as they appear in file names.
FEH = ["m4.00", "m3.50", "m3.00", "m2.50", "m2.00", "m1.75", "m1.50", "m1.25", "m1.00",
       "m0.75", "m0.50", "m0.25", "p0.00", "p0.25", "p0.50"]


def archive_name(feh: str, vvcrit: str = "0.4") -> str:
    return f"MIST_v1.2_feh_{feh}_afe_p0.0_vvcrit{vvcrit}_EEPS.txz"


def fetch(name: str, dest_dir: Path = CACHE) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    part = dest.with_suffix(dest.suffix + ".part")
    url = BASES[name.split("_")[1]] + name

    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
        if r.headers.get("Content-Length") is None:
            raise SystemExit(f"{name}: the server gave no size, so the download cannot be checked")
        total = int(r.headers["Content-Length"])
    if dest.exists():
        if dest.stat().st_size == total:
            print(f"{name}: already complete ({total / 1e6:.1f} MB)")
            return dest
        raise SystemExit(f"{dest} is {dest.stat().st_size} bytes, server says {total}; delete it")

    have = part.stat().st_size if part.exists() else 0
    if have > total:
        raise SystemExit(f"{part} is larger than the server's file; delete it")
    if have < total:
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"})
        with urllib.request.urlopen(req, timeout=60) as r, part.open("ab") as out:
            if have and r.status != 206:
                raise SystemExit(f"{name}: server ignored the resume request (HTTP {r.status})")
            while chunk := r.read(1 << 20):
                out.write(chunk)
                have += len(chunk)
                print(f"\r{name}: {have / 1e6:7.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()

    if part.stat().st_size != total:
        raise SystemExit(f"{name}: got {part.stat().st_size} bytes, expected {total}; rerun to resume")
    part.rename(dest)
    return dest


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    args = FEH if argv == ["all"] else argv
    names = [a if a.endswith(".txz") else archive_name(a) for a in args]
    bad = [a for a in args if not a.endswith(".txz") and a not in FEH]
    bad += [n for n in names if n.split("_")[1:2] not in [[v] for v in BASES]]
    if bad:
        raise SystemExit(f"unknown {bad}; use a [Fe/H] label from {FEH} or a full archive name")
    for name in names:
        print(fetch(name))


if __name__ == "__main__":
    main(sys.argv[1:])
