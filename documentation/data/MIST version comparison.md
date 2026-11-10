# MIST v1.2 against v2.5

Phase 1, step 3 of the build plan: compare the two releases before the dataset format is fixed.
Written 11 November 2026 from four archives, all rotating (v/vcrit = 0.4) with [α/Fe] = 0:

| Release | [Fe/H] = 0 | [Fe/H] = −3.0 |
| --- | --- | --- |
| v1.2 | `MIST_v1.2_feh_p0.00_afe_p0.0_vvcrit0.4_EEPS.txz` (107 MiB) | `MIST_v1.2_feh_m3.00_afe_p0.0_vvcrit0.4_EEPS.txz` (75 MiB) |
| v2.5 | `MIST_v2.5_feh_p000_afe_p0_vvcrit0.4_EEPS.txz` (186 MiB) | `MIST_v2.5_feh_m300_afe_p0_vvcrit0.4_EEPS.txz` (129 MiB) |

The numbers below come from `stellarforge.mist.read_archive` on these files and from the download
directory listings at https://mist.science/data/. The per-track tables are reproduced by running
`python -m stellarforge.mist inventory <archive>` on each archive.

## Summary

| Question | v1.2 | v2.5 |
| --- | --- | --- |
| MESA revision | 7503 | 11701 |
| Tracks per metallicity | 196 at both [Fe/H] | 171 at 0, 155 at −3.0: the mass grid differs between metallicities |
| Mass range | 0.1–300 M☉ | 0.1–300 M☉ |
| Finest mass step | 0.01 M☉ (0.30–0.40 M☉), 0.02 M☉ around 1–2.8 M☉ | 0.01 M☉ from 0.70 to 1.20 M☉ |
| [Fe/H] values | 15, −4.0 to +0.5 | 17, −4.0 to +0.5 (adds −2.75 and −2.25) |
| [α/Fe] values | 0 only | −0.2, 0, +0.2, +0.4, +0.6 |
| Rotation sets | 0 and 0.4 | 0 and 0.4 |
| Z_init at [Fe/H] = 0 | 0.014286 (Asplund et al. 2009 scale) | 0.016358 (GS98 scale) |
| Z_init at [Fe/H] = −3.0 | 1.4286 × 10⁻⁵ | 1.722 × 10⁻⁵ |
| Columns per track | 77 | 168 (94 added, 3 dropped) |
| Primary EEPs | 10, ending at 1710 | 11, adding 1420 and ending at 1721 |
| Download, rotating, [α/Fe] = 0 | 15 archives, 1.46 GB | 17 archives, 2.92 GB |
| Download, every v2.5 archive | — | 168 archives, 28.3 GB |
| Citation | Choi et al. 2016; Dotter 2016 (published) | Dotter et al. 2026, in press |

## Coverage and how tracks end

**v1.2 does not stop after core helium burning below [Fe/H] −2.0.** The plan says it does, but at
[Fe/H] −3.0, 32 of 196 tracks reach the white-dwarf cooling sequence and 44 reach the end of carbon
burning. What v1.2 does have at −3.0 is a ragged set of endings: 72 low-mass tracks stop at the
start of the thermally pulsing AGB, 15 stop at the start of core helium burning, and two (17 and
20 M☉) stop at the tip of the red giant branch. Neighbouring masses often end differently (1.16 M☉
reaches the white dwarf, 1.14 and 1.18 M☉ stop on the AGB).

**v2.5 has a large hole at [Fe/H] −3.0.** Its grid there has no tracks at all between 9 and 40 M☉,
and the five tracks from 7 to 9 M☉ stop at the zero-age main sequence. So nothing between 6.5 and
40 M☉ evolves past the main sequence: the whole core-collapse range Phase 2 needs. Fourteen tracks
between 150 and 300 M☉ also stop at the start of core helium burning.

At [Fe/H] = 0 the two releases agree on the broad picture: stars below about 0.6 M☉ stop at the end
of the main sequence, most stars from 0.65–0.7 to 6.5–7.4 M☉ reach the white-dwarf cooling sequence,
and massive stars end at carbon burning. v2.5 has fewer odd endings in the low- and intermediate-mass
range (one post-AGB stop at 4.8 M☉ against five in v1.2).

**Low-mass stars.** The plan says stars of 0.7 M☉ and below stop at the end of the main sequence. In
both releases at [Fe/H] = 0 that is true only up to 0.55–0.60 M☉; the 0.65 and 0.7 M☉ tracks reach the
post-AGB or the white-dwarf cooling sequence.

## EEPs, columns and units

- Both releases use the same `.eep` text layout and the same header lines, so one parser reads both.
  v2.5 archives also hold `input_XYZ` and `input_initial_xa.data` beside the tracks.
- Primary EEPs 1–1409 have the same numbers in both. v2.5 adds EEP 1420 and moves the final EEP from
  1710 to 1721. **The definitions of 1420 and 1721 are not checked**; Dotter et al. 2026 is in press
  and not in `documentation/references/`. `mist.py` labels 1721 "assumed" white-dwarf cooling because
  it ends the longest tracks, as 1710 does in v1.2.
- v2.5's white-dwarf tracks end with MIST phase label −9, which v1.2 does not use; its meaning needs
  the v2.5 paper.
- All 14 columns `mist.py` keeps have the same names in both releases. v2.5 adds 94 columns (mostly
  central and surface abundances of individual isotopes, plus `apsidal_constant_k2`) and drops
  `log_surf_z`, `surface_b11` and `v_wind_Km_per_s`.
- Neither release puts units in its headers; both follow MESA's conventions.

## Abundance scale

The same [Fe/H] label means a different metal content: at [Fe/H] = 0, v2.5's Z_init is 15% higher
than v1.2's (GS98 against Asplund et al. 2009). Exports must name the release and its abundance scale
in `meta.dataset`, and the two releases must never be blended.

## Disk budget

The project's budget is about 5 GB. v1.2's rotating set (1.46 GB) leaves room for the processed grid
(about 0.4 GB), the web data (about 150 MB), the papers and the 1 GB results cap. v2.5's rotating
[α/Fe] = 0 set (2.92 GB) also fits, but leaves about 0.5 GB of slack. Any second [α/Fe] value or the
non-rotating set would not fit unless archives are deleted after conversion. Since the archives are
read in place, they cannot be deleted without giving up that design.

## Recommendation

Keep v1.2 as the default, as the plan proposes:

1. It is published; v2.5 is in press and its new EEPs and phase label are undefined until the paper
   can be read.
2. Its mass grid is the same at every metallicity, which keeps EEP interpolation cells regular.
   v2.5's grid changes with [Fe/H], and at −3.0 it has no evolved tracks from 6.5 to 40 M☉.
3. It uses half the disk.

v2.5's advantages, the [α/Fe] axis and the 0.01 M☉ steps around the Sun's mass, do not change any
Phase 1 deliverable. `mist.py` reads both releases through a per-version column map and EEP table,
so v2.5 can be added later without changing the format.

**Decision (11 November 2026):** v1.2, rotating (v/vcrit = 0.4), [α/Fe] = 0, all 15 metallicities.
v2.5 can be revisited once Dotter et al. 2026 is published and its EEP definitions are checked.

## Corrections to the build plan

Applied in revision 4 of the build plan (11 November 2026), with notes in `Source checks.md`.

- Phase 1 coverage table: v1.2 tracks below [Fe/H] −2.0 are not cut after core helium burning; many
  run to the white dwarf or carbon burning, with irregular endings.
- Phase 1 coverage table: at [Fe/H] = 0, stars down to 0.65 M☉ evolve past the main sequence.
- Phase 1, step 5: the safeguard list should add that EEP 808 has two meanings, decided by the
  track's `low-mass` or `high-mass` type.
