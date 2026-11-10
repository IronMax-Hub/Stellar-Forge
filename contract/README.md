# Data contract

`fixture.json` is the one shape both stacks agree on. `tests/test_contract.py` (pytest) checks that
`stellarforge/export.py` produces it; `web/src/__tests__/contract.test.ts` (Vitest) checks that the
web loader parses it. Both assert the same `schema_version`. The tests check shape, not values.

Changing the format: edit the fixture, raise `schema_version` by one in the fixture,
`stellarforge/__init__.py` and `web/src/data/types.ts`, and update both sides until both tests pass.

Schema version 1. The fixture's numbers are hand-written test data, not physics.

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

## `track` — one star's evolution

All arrays have one entry per track point and the same length.

| Field | Type | Unit |
| --- | --- | --- |
| `provenance` | `published`, `interpolated`, `derived` or `predicted` | where the track came from |
| `flags` | list of strings | validity warnings, such as `near_grid_boundary` |
| `age_yr` | numbers | years since the start of the track |
| `log_l_lsun` | numbers | log10 of luminosity in solar luminosities |
| `log_teff_k` | numbers | log10 of effective temperature in kelvin |
| `log_r_rsun` | numbers | log10 of radius in solar radii |
| `rgb` | `[r, g, b]` triples | the star's display colour, sRGB, each channel 0–1 |

Field names end in their unit (`_msun`, `_lsun`, `_rsun`, `_k`, `_yr`, `_au`, `_mearth`) and logs
start with `log_`.
