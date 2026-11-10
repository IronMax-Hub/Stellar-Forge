# Data contract

`fixture.json` is the one shape both stacks agree on. `tests/test_contract.py` (pytest) checks that
`stellarforge/export.py` produces it; `web/src/__tests__/contract.test.ts` (Vitest) checks that the
web loader parses it. Both assert the same `schema_version`. The tests check shape, not values.

Changing the format: edit the fixture, raise `schema_version` by one in the fixture,
`stellarforge/__init__.py` and `web/src/data/types.ts`, and update both sides until both tests pass.

Schema version 2 (Phase 1: the `track` block moved inside a `grid` block). The fixture's numbers are hand-written test data, not physics.

## `meta` — carried by every export

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | contract version |
| `generator.name`, `.version`, `.git_commit` | strings | the code that made the file |
| `dataset` | string | the published data the numbers came from, with its abundance scale |
| `models` | object of strings | which prescription produced each kind of result |
| `inputs` | object of numbers | the run's parameters; names carry units (`mass_msun`), `feh` is [Fe/H] in dex |
| `seed` | integer or null | random seed, null when nothing is random |
| `created` | string | UTC time, ISO 8601 |
| `references` | list of `{key, citation, doi}` | sources used, taken from `stellarforge/references.json` |

## `grid` — one [Fe/H] slice of the Star Builder grid

Written by `python -m stellarforge.export web` as `web/public/data/tracks_feh_<±x.x>.json`, one
file per [Fe/H] value. The web sliders snap to `feh_values` and `mass_values_msun`.

| Field | Type | Meaning |
| --- | --- | --- |
| `feh` | number | this file's [Fe/H], dex |
| `feh_values` | numbers | every exported [Fe/H] |
| `files` | strings | the file for each entry of `feh_values` |
| `mass_values_msun` | numbers | every exported initial mass, M☉; one track per mass, same order |
| `tracks` | list of `track` | one per mass |

## `track` — one star's evolution

All arrays have one entry per track point and the same length.

| Field | Type | Unit or meaning |
| --- | --- | --- |
| `mass_msun` | number | initial mass, M☉ |
| `feh` | number | [Fe/H], dex |
| `method` | string | how the track was made: MIST grid track, EEP interpolation, or the nearest MIST track used |
| `provenance` | `published`, `interpolated`, `derived` or `predicted` | where the track's MIST values came from |
| `ending` | string | the last primary EEP the track reaches, such as `white-dwarf cooling sequence` |
| `flags` | list of strings | validity warnings, such as `nearest_track_used` |
| `phase_names` | object of strings | MIST phase number (as a string key) → name for this track; MIST's `high-mass` tracks reuse the numbers with other meanings |
| `field_provenance` | object of provenances | the provenance of each array below |
| `age_yr` | numbers | years since the start of the track |
| `mass_now_msun` | numbers | current mass, M☉ |
| `log_l_lsun` | numbers | log10 of luminosity in solar luminosities |
| `log_teff_k` | numbers | log10 of effective temperature in kelvin |
| `log_r_rsun` | numbers | log10 of radius in solar radii |
| `phase` | integers | MIST phase number; see `phase_names` |
| `rgb` | `[r, g, b]` triples | the star's display colour, sRGB, each channel 0–1 |

Field names end in their unit (`_msun`, `_lsun`, `_rsun`, `_k`, `_yr`, `_au`, `_mearth`) and logs
start with `log_`.
