"""mist.py reads a small synthetic archive laid out exactly like a MIST v1.2 one."""

import io
import tarfile

from stellarforge import mist

COLS = ["star_age", "star_mass", "log_L", "log_Teff", "phase"]


def eep_text(mass: float, eeps: list[int], rows: list[list[float]]) -> str:
    header = [
        "# MIST version number  = 1.2",
        "# MESA revision number =     7503",
        "# ----",
        "#  Yinit        Zinit   [Fe/H]   [a/Fe]  v/vcrit",
        "# 0.2703  1.42857E-02     0.00     0.00     0.40",
        "# ----",
        "#     initial_mass   N_pts   N_EEP   N_col   phase        type",
        f"# {mass:.10E}    {len(rows)}      {len(eeps)}      {len(COLS)}     YES    low-mass",
        "# EEPs:  " + "  ".join(str(e) for e in eeps),
        "# ----",
        "#  " + "  ".join(str(i) for i in range(1, len(COLS) + 1)),
        "#  " + "  ".join(COLS),
    ]
    return "\n".join(header + ["  ".join(f"{x:.6E}" for x in r) for r in rows]) + "\n"


def make_archive(path):
    files = {
        "00100M.track.eep": eep_text(1.0, [1, 202, 353, 454, 605, 631, 707, 808, 1409, 1710],
                                     [[1e3, 1, 0, 3.6, -1], [1.3e10, 0.5, -4, 4.5, 6]]),
        "00050M.track.eep": eep_text(0.5, [1, 202, 353, 454], [[1e3, 0.5, 0, 3.5, -1],
                                                               [1e11, 0.5, -1, 3.6, 0]]),
    }
    with tarfile.open(path, "w:xz") as tar:
        for name, text in files.items():
            data = text.encode("ascii")
            info = tarfile.TarInfo(f"MIST_test/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_reads_tracks_and_endings(tmp_path):
    path = tmp_path / "test.txz"
    make_archive(path)
    tracks = {t.initial_mass_msun: t for t in mist.read_archive(path)}
    assert set(tracks) == {0.5, 1.0}
    sun = tracks[1.0]
    assert (sun.feh, sun.zinit, sun.vvcrit, sun.version) == (0.0, 0.0142857, 0.4, "1.2")
    assert sun.n_rows == sun.n_pts == 2
    assert sun.final_age_yr == 1.3e10 and sun.final_phase == 6
    assert sun.ending == "white-dwarf cooling sequence"
    assert tracks[0.5].ending == "end of main sequence"


def test_inventory_report(tmp_path):
    path = tmp_path / "test.txz"
    make_archive(path)
    report = mist.inventory([path])
    assert "| 454: end of main sequence | 0 | 1 | 0.5 |" in report
    assert "| 1710: white-dwarf cooling sequence | 6 | 1 | 1 |" in report
    # The synthetic files lack most kept columns; the report must say so, not hide it.
    assert "missing here:** c_core_mass, center_h1" in report


def test_eep_808_depends_on_star_type():
    track = mist.parse_eep(eep_text(20.0, [1, 202, 353, 454, 605, 631, 707, 808],
                                    [[1e3, 20, 0, 4.5, -1], [1e7, 15, 5, 4.0, 5]]))
    assert track.ending == "start of thermally pulsing AGB"  # header says low-mass
    track.star_type = "high-mass"
    assert track.ending == "end of core carbon burning"


def test_v25_eeps_and_unknown_eeps():
    track = mist.parse_eep(eep_text(1.0, [1, 202, 353, 454, 605, 631, 707, 808, 1409, 1420, 1721],
                                    [[1e3, 1, 0, 3.6, -1], [1.2e10, 0.5, -4, 4.5, -9]]))
    track.version = "2.5"
    assert track.ending == "white-dwarf cooling sequence (assumed for v2.5)"
    track.eeps = [1, 999]
    assert track.ending == "EEP 999 (not a known primary EEP)"
