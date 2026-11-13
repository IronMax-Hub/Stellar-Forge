# Stellar-Forge

Stars and their planets from published physics. Python computes every result from published stellar
models and datasets; a small web app only displays what Python exported, and labels every value with
where it came from (published, interpolated, substituted, derived or predicted).

It runs on one ordinary desktop: no cloud compute, no full stellar-evolution code.

## What works now

| Phase | What it does | Status |
| --- | --- | --- |
| 0 | Scaffold, the shared data contract, rendering code copied from Aion Forge | done |
| 1 | Any star from 0.1 to 300 M☉ and [Fe/H] −4.0 to +0.5, from the MIST v1.2 tracks: EEP interpolation, **Star Builder** web view with an HR diagram | done |
| 2 | The remnant each star leaves: white dwarfs with cooling tracks, neutron stars, black holes, pair-instability supernovae; **Remnants** view | done |
| 3 | Experiments across mass × metallicity: lifetime and remnant maps, remnant-mass curves, an IMF population; **Experiments** view | done |
| 4–8 | Stellar structure lab, planet formation, planet fates, the full observatory app, an optional local API | planned |

The full plan, with every validation check and its result, is
[documentation/Stellar-Forge Build Plan.md](documentation/Stellar-Forge%20Build%20Plan.md). Every
claim it makes about a source is checked in [documentation/Source checks.md](documentation/Source%20checks.md).

## Quick start

You need Python 3.12 (installed into `.venv` by [uv](https://docs.astral.sh/uv/)), Node 22, `make`
and `curl`, and about 2 GB of free disk for the downloaded data.

```bash
make setup         # Python and web dependencies
make data          # download MIST v1.2 (~1.5 GB) and Bédard et al. 2020 (0.6 MB), convert MIST
make export        # write the Star Builder grid to web/public/data (~140 MB)
make experiments   # run the six Phase 3 experiments into results/ and copy them for the web
make dev           # start the web app
make check         # ruff, pytest, TypeScript, ESLint and Vitest: must pass before every commit
```

Downloads go to `~/.cache/stellar-forge/`. MIST archives are read in place, never unpacked.

Run one experiment with its own grid:

```bash
.venv/bin/python -m stellarforge.experiments lifetime-map --feh=-4:0.5:0.1 --masses=200
```

Each run writes `results/<experiment>/<time>/` with `result.json`, `figure.png` and `run.json`. The
same command on the same code gives a byte-identical `result.json`.

## How it is built

- **`stellarforge/`** — all physics, including interpolation:
  - `mist.py` reads and converts the MIST archives; `evolution.py` builds a track for any mass and
    [Fe/H] by blending neighbouring tracks at equal evolutionary phase, never across tracks that end
    differently, and never outside the grid;
  - `remnants.py` gives each star's remnant, every threshold a named constant with its citation;
  - `experiments.py` runs the Phase 3 experiments; `export.py` writes the JSON the web app reads.
- **`web/`** — a Vite, React and Three.js app that draws, animates and never computes a physical value.
  Sliders snap to the grid Python exported.
- **`contract/`** — one JSON fixture both sides are tested against. Field names carry their units
  (`_msun`, `_yr`, `log_…`); see [contract/README.md](contract/README.md).
- **`documentation/data/`** — generated reports: MIST coverage, the MIST v1.2 / v2.5 comparison, and
  the interpolation check.

## Published sources

The main ones; every export lists its references in `meta.references`, and the full list with DOIs
is `stellarforge/references.json`.

- Stellar tracks: MIST v1.2, Choi et al. 2016 (ApJ 823, 102); Dotter 2016 (ApJS 222, 8); built with
  MESA, Paxton et al. 2011
- Remnants: Fryer et al. 2012 (core collapse); Belczynski et al. 2016 and Heger & Woosley 2002 (pair
  instability); Cummings et al. 2018 (white-dwarf masses); Bédard et al. 2020 (white-dwarf cooling)
- Population: Kroupa 2001 (initial mass function)

Results are single-star models: most massive stars interact with a companion (Sana et al. 2012), and
binary evolution is not covered. Known limits of the data, such as MIST tracks that stop early, are
labelled on every affected result rather than hidden.

## Provenance of copied code

Rendering code (star colour, the black-hole lensing view, planet and system views) was copied from
the author's Aion Forge project and adapted; [PROVENANCE.md](PROVENANCE.md) records every file, its
checksum and each change.

Downloaded papers and data stay out of Git.
