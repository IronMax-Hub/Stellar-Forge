# Data contract

`fixture.json` is the one shape both stacks agree on. `tests/test_contract.py` (pytest) checks that
`stellarforge/export.py` produces it; `web/src/__tests__/contract.test.ts` (Vitest) checks that the
web loader parses it. Both assert the same `schema_version`. The tests check shape, not values.

Changing the format: edit the fixture, raise `schema_version` by one in the fixture,
`stellarforge/__init__.py` and `web/src/data/types.ts`, and update both sides until both tests pass.

Schema version 10 (the `timeline` block and each `population` cell's `timeline_file`; version 9 added validity `flags` on each `population` cell; version 8 added the `population` and `systems` blocks; version 7 added `profiles`, version 6 `polytropes`, version 5 the `substituted` provenance, version 4 the
`experiment` block; version 3 added `remnant`, version 2 moved
`track` inside `grid`). The fixture's numbers are hand-written test data, not physics.

A document is `meta` plus one or more blocks: Star Builder files carry `grid`, experiment results
carry `experiment`, `polytropes.json` carries `polytropes`, `zams.json` carries `profiles`,
`planets/population.json` carries `population`, each `planets/systems_<nnn>.json` carries
`systems`, and each `planets/timeline_<nnn>.json` and `planets/solar_system.json` carry `timeline`. The fixture holds every block.

## `meta` — carried by every export

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | contract version |
| `generator.name`, `.version`, `.git_commit` | strings | the code that made the file; `.git_commit` ends in `+changes` when `stellarforge/` differed from that commit |
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
| `method` | string | how the track was made: MIST grid track, EEP interpolation, or the nearest MIST track used, with its distance in log mass and [Fe/H] |
| `provenance` | `published`, `interpolated`, `substituted`, `derived` or `predicted` | where the track's MIST values came from; `substituted`: the nearest MIST track stands in, and `method` gives its distance |
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
| `remnant` | `remnant` | what the star leaves behind |

## `remnant` — what a star leaves behind (`stellarforge/remnants.py`)

Fields marked "or null" are null when there is no remnant or MIST gives no value.

| Field | Type | Unit or meaning |
| --- | --- | --- |
| `type` | `white dwarf`, `neutron star`, `black hole`, `none`, `not yet` or `not predicted` | `none`: destroyed by a pair-instability supernova; `not yet`: still on the main sequence where its track ends; `not predicted`: the track stops too early, or lacks a core mass |
| `mass_msun` | number or null | remnant (gravitational) mass, M☉ |
| `radius_km` | number or null | white dwarf: radius at the end of its cooling track; neutron star: 12 km; black hole: horizon radius |
| `provenance` | provenance | `predicted` for core collapse; the track's provenance for a white dwarf's MIST mass (the track's own `provenance` says where the final and core masses came from); `derived` when there is no remnant |
| `prescription` | string | the rule that gave `type` and `mass_msun` |
| `how` | string | how it formed, in a sentence |
| `alternative.prescription`, `.type`, `.mass_msun` | string, type, number or null | the other prescription's answer (rapid for delayed; Cummings et al. 2018 for a white dwarf) |
| `final_mass_msun`, `he_core_mass_msun`, `co_core_mass_msun` | number or null | the track's last state, M☉; null where MIST gives no core mass |
| `flags` | list of strings | validity warnings; always includes `single_star_assumed` |
| `cooling` | object or null | white dwarfs: `cooling_age_yr`, `log_l_lsun`, `log_teff_k`, `radius_km`, equally long |


Field names end in their unit (`_msun`, `_lsun`, `_rsun`, `_k`, `_yr`, `_au`, `_mearth`) and logs
start with `log_`.

## `experiment` — one experiment's result (`stellarforge/experiments.py`)

Written to `results/<experiment>/<time>/result.json` and, with `--export`, to
`web/public/data/experiments/<experiment>.json`.

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | the command that made it, such as `lifetime-map` |
| `title`, `summary` | strings | what it shows, in words |
| `panels` | list of `panel` | the result's figures |

A `panel` is a heatmap (one row per [Fe/H], one cell per `x_values` entry), curves (one row per
curve over `x_values`) or a table (one cell per `columns` entry).

| Field | Type | Meaning |
| --- | --- | --- |
| `title` | string | the panel's title |
| `kind` | `heatmap`, `curves` or `table` | how it is drawn |
| `x_label`, `y_label`, `value_label` | strings | axis and value names, with units |
| `log_x`, `log_values` | booleans | draw x, or the values, on a log scale |
| `x_values` | numbers | heatmap columns or curve x (empty for a table) |
| `columns` | strings | table column names (empty otherwise) |
| `rows[].label` | string | the row's or curve's name |
| `rows[].y` | number or null | a heatmap row's y value |
| `rows[].values` | numbers or nulls | one per cell; null where the cell has no number |
| `rows[].labels` | strings or nulls | one per cell: a word shown instead of the number, such as `track incomplete` or a remnant type |
| `rows[].provenance` | provenances or nulls | one per cell: where its value came from |

## `polytropes` — Lane–Emden polytropes (`stellarforge/structure.py`)

Written by `python -m stellarforge.export polytropes` as `web/public/data/polytropes.json`. The
view's n slider snaps to `n_values`. Every model has the same number of points, evenly spaced in
radius. Fields without a unit are dimensionless.

| Field | Type | Meaning |
| --- | --- | --- |
| `n_values` | numbers | every exported polytropic index, one model each, same order |
| `models[].n` | number | the polytropic index |
| `models[].provenance` | provenance | always `derived`: solved by Stellar-Forge |
| `models[].flags` | strings | `no_surface_profile_cut_at_xi_50` for n = 5, which has no surface: its radii are ξ / 50 |
| `models[].xi1` | number or null | the first zero of θ, the surface; null for n = 5 |
| `models[].mass_constant` | number | −ξ₁² θ′(ξ₁); √3 for n = 5 |
| `models[].density_concentration` | number or null | central over mean density, ρc/ρ̄; null for n = 5 |
| `models[].sun_rho_c_kg_m3`, `.sun_p_c_pa`, `.sun_t_c_k` | numbers or null | the polytrope scaled to 1 M☉ and 1 R☉, ideal gas with μ = 0.617 (see `meta.models`): central density, pressure and temperature; null for n = 5 |
| `models[].radius_frac` | numbers | r/R, from 0 to 1 |
| `models[].xi` | numbers | the Lane–Emden radius ξ |
| `models[].theta` | numbers | θ(ξ); also T/Tc for an ideal gas of uniform composition |
| `models[].mass_frac` | numbers | m(r)/M |
| `models[].density_frac`, `.pressure_frac` | numbers | ρ/ρc and P/Pc |

## `profiles` — zero-age main-sequence structure (`stellarforge/structure.py`)

Written by `python -m stellarforge.export zams` as `web/public/data/zams.json`: one `profile` per
star in `models`. Arrays run from the centre to the surface, one entry per point, all equally long;
the outer half of the mass is sampled evenly in log(1 − m/M). Fields without a unit are
dimensionless.

| Field | Type | Meaning |
| --- | --- | --- |
| `mass_msun`, `feh` | numbers | the star: initial mass, M☉, and [Fe/H], dex |
| `provenance` | provenance | always `derived`: solved by Stellar-Forge |
| `method` | string | how the model was made |
| `flags` | strings | validity warnings, such as `kww_formulae_not_yet_source_checked` |
| `x`, `y`, `z` | numbers | mass fractions of hydrogen, helium and metals |
| `log_l_lsun`, `log_r_rsun`, `log_teff_k` | numbers | the model's luminosity, radius and effective temperature |
| `log_t_c_k`, `log_rho_c_kg_m3`, `p_c_pa` | numbers | central temperature, density (kg/m³) and pressure (Pa) |
| `energy_core_r_frac` | number | r/R inside which 99% of the luminosity is produced |
| `pp_share` | number | the pp chain's share of the energy generated (the rest is CNO) |
| `mist` | object or null | MIST's zero-age star (EEP 202) of the same mass and [Fe/H]: `provenance` (`published`), the five `log_` values above, and `delta_<name>`, model minus MIST in dex |
| `r_frac`, `m_frac`, `l_frac` | numbers | r/R, m/M and L(r)/L |
| `t_frac`, `rho_frac`, `p_frac` | numbers | T/Tc, ρ/ρc and P/Pc |
| `eps_pp_w_kg`, `eps_cno_w_kg` | numbers | energy generation by the pp chain and the CNO cycle, W/kg |
| `kappa_m2_kg` | numbers | Rosseland mean opacity, m²/kg |
| `nabla`, `nabla_ad`, `nabla_rad` | numbers | the actual, adiabatic and radiative temperature gradients d ln T / d ln P |
| `convective` | booleans | true where the Schwarzschild criterion gives convection |

## `population` — the planet grid (`stellarforge/experiments.py`, Phase 5)

Written by `make planets` as `web/public/data/planets/population.json`. Everything in it is a
model prediction; the calibration labels say how far to trust each cell.

| Field | Type | Meaning |
| --- | --- | --- |
| `star_masses_msun`, `feh_values` | numbers | the grid; the view's selectors snap to these |
| `classes` | strings | the planet classes, in the classifier's order |
| `calibration_mass_msun`, `calibration_feh` | `[low, high]` | the calibration range: cells inside are `prediction`, outside `extrapolation` |
| `cells` | list of cells | one per star mass and [Fe/H], [Fe/H]-major (all masses of the first [Fe/H] first) |
| `conclusions[].statement` | string | a conclusion about the population, in words |
| `conclusions[].label` | calibration label | `prediction` when it holds in every sensitivity run, else `parameter-sensitive` |

Calibration labels are `observational constraint`, `prediction`, `parameter-sensitive` or
`extrapolation`.

| Cell field | Type | Meaning |
| --- | --- | --- |
| `m_star_msun`, `feh` | numbers | the star |
| `n_systems`, `seed` | integers | disks simulated, and the random seed that reproduces them |
| `calibration` | calibration label | `prediction` inside the calibration range, `extrapolation` outside |
| `provenance` | provenance | always `predicted` |
| `host_share` | object of numbers | class → share of systems with at least one planet of that class |
| `planets_per_star` | number | planets (≥ 0.1 M⊕) per system |
| `systems_with_count` | integers | entry k: systems with exactly k planets |
| `a_ice_au` | number | the snow line, AU |
| `systems_file` | string | the cell's sample systems, relative to `web/public/data/` |
| `timeline_file` | string | their timelines (the `timeline` block), relative to `web/public/data/` |
| `flags` | strings | validity warnings: each survey check the model fails, with its numbers (ground rule 6) |

## `systems` — one cell's sample systems

The first 200 systems of a cell (the disks are drawn at random, so this is an unbiased sample).

| Field | Type | Meaning |
| --- | --- | --- |
| `m_star_msun`, `feh`, `seed`, `calibration`, `a_ice_au` | as in the cell | the cell they belong to |
| `systems[].index` | integer | the system's number in the cell |
| `systems[].f_g0`, `.f_d0` | numbers | the disk's gas and solids relative to the minimum-mass solar nebula |
| `systems[].tau_disk_yr` | number | the gas depletion time, years |
| `systems[].planets` | list of planets | from the inside out; empty when nothing reached 0.1 M⊕ |

| Planet field | Type | Meaning |
| --- | --- | --- |
| `class` | class | `gas giant`, `ice giant`, `sub-Neptune`, `super-Earth` or `terrestrial` |
| `mass_mearth` | number | total mass, M⊕ |
| `radius_rearth` | number | display radius from Chen & Kipping 2017, R⊕; never used to classify |
| `a_au`, `a_form_au` | numbers | the orbit when the gas is gone, and where the core grew, AU |
| `f_env` | number | envelope fraction, M_env / M_p |
| `core` | `ice-rich` or `rock-dominated` | ice-rich when the core grew beyond the snow line |
| `provenance` | provenance | always `predicted` |
| `radius_provenance` | provenance | always `derived` |

## `timeline` — planets through their star's life (`stellarforge/planets/coevolution.py`, Phase 6)

Written by `make planets` (or `python -m stellarforge.experiments timelines --export`) as
`web/public/data/planets/timeline_<nnn>.json`, one per `systems_<nnn>.json` and continuing it
planet by planet in the same order, and as `planets/solar_system.json`, the reference case.

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | what the file shows: the cell, or `Solar System` |
| `m_star_msun`, `feh` | numbers | the star |
| `systems_file` | string or null | the Phase 5 systems this continues; null for the Solar System |
| `star` | object | the star at the exported ages (below) |
| `systems[].index` | integer | the system's number in the cell (as in `systems_file`) |
| `systems[].planets` | list of planets | in the order of `systems_file` |

| Star field | Type | Meaning |
| --- | --- | --- |
| `provenance`, `method`, `ending`, `flags` | as in `track` | where the star's track came from, and its warnings |
| `age_yr` | numbers | the exported ages; every other list has one entry per age |
| `mass_msun`, `radius_au`, `l_lsun`, `teff_k` | numbers | the star; radius in AU so it can be drawn with the orbits |
| `hz_inner_au`, `hz_outer_au` | numbers or null | Kopparapu et al. 2013 runaway and maximum greenhouse limits; null where Teff is outside 2,600–7,200 K |
| `phase` | strings | MIST phase name |
| `rgb` | `[r, g, b]` per age | display colour from Teff (`stellarforge/colour.py`), derived |

| Planet field | Type | Meaning |
| --- | --- | --- |
| `name` | string or null | named planets only (the Solar System) |
| `class_at_formation`, `class_final` | classes | Phase 5's class when the gas is gone, and after escape |
| `mass_mearth`, `final_mass_mearth` | numbers | total mass then and at the end, M⊕ |
| `final_f_env` | number | envelope fraction at the end |
| `orbit_sample`, `orbit_a_au` | integers, numbers | the orbit as knots: `orbit_a_au[i]` at age `age_yr[orbit_sample[i]]`; between knots it changes linearly with the sample index. The last knot is the last age the planet exists |
| `fate` | string | `engulfed`, `unbound`, `orbits white dwarf`, `orbits neutron star`, `orbits black hole` or `unresolved` (the track ends first) |
| `closest_approach_rstar` | number | the smallest orbit in stellar radii (1 when engulfed) |
| `deciding_phase` | string | the MIST phase at the closest approach |
| `xuv_dose_earth` | number | XUV dose since the disk's end, Earth doses |
| `shoreline` | `kept` or `lost` | the cosmic-shoreline label (Zahnle & Catling 2017 slope, Aion Forge's K = 10) |
| `air_retained` | number | the shoreline's share of air kept (Aion Forge's retention curve) |
| `events[]` | `{age_yr, kind, detail}` | `formed`, `enters habitable zone`, `leaves habitable zone`, `crosses shoreline`, `envelope stripped`, `class changed`, `engulfed`, `unbound`, `orbits remnant` or `track ends`; `detail` says it in words |
| `flags` | strings | validity warnings, such as the shoreline and escape disagreeing |
| `provenance` | provenance | always `predicted` |
