# Scientific audit

14 November 2026 · whole repository at `development` (`7667238`, Phase 5 merged) · companion to [Stellar-Forge Build Plan](Stellar-Forge%20Build%20Plan.md) and [Source checks](Source%20checks.md)

Every physics module was read against the paper or dataset it names, using the local copies in `references/papers/`. The checks were formula by formula, with recomputation where a number could be checked. Validation claims were compared with the tests and the exported data, and `web/` was searched for physics. `make check` passed before the audit (104 pytest, 9 Vitest). No code was changed.

**Verdict.** The implemented formulas are faithful to their sources: no transcription error was found in any equation the code cites. The problems are about consistency and honesty, not arithmetic:
- the planet model joins two papers' disk models at one point;
- validity flags promised by ground rule 6 are missing;
- one printed equation is silently corrected;
- several records are out of date.

## Status: all findings addressed (14 November 2026)

| Finding | What was done |
| --- | --- |
| H1 | every planet cell carries one `survey_check_failed` flag per failed check, shown in the Planets view; contract schema version 9 |
| H2 | blended stars carry `near_grid_boundary` and `interpolation_error_may_exceed_0.02_dex` (from the leave-one-out results) |
| H3 | `ida_lin_2013.viscous_couple_radius_au`: r_m,0 = (τ_dep / 7 × 10⁴ yr)(α/10⁻³)(M★/M☉)^1/2 AU from Paper VII eqs. 32–33, growing as exp(2t/3τ_dep); grid re-run, still 1 of 7 survey checks pass |
| M1 | Source checks row for eq. 31 |
| M2 | sub-Neptunes need M_p ≥ 2 M⊕; envelope addition in mergers recorded as a shortcut |
| M3 | the Sun-check margin stated in Validation; MIST's calibrated solar model is not in the released archives |
| M4, M5 | Validation and Source checks updated (69 claims; two rows closed, two added) |
| L1 | the missing ψ and screening stated with the pp/CNO result; screening would widen the gap, not close it |
| L2 | core growth uses the core's mass |
| L3 | unused 2004a/2008a formulas and their tests removed; tests now cover the Paper VII rates and r_m |
| L4 | Phase 6 requires Python to export orbital positions and ring iciness before the 3D view is wired in |
| L5 | plan reuse table names the real modules |
| L6 | measured: blending in log age is not better (worst error 0.255 against 0.197 dex along mass), so the linear blend stays |

## Findings, most serious first

### High

**H1. Planet cells carry no warnings, though 6 of 7 survey checks fail.** All 72 cells inside the 0.2–1.5 M☉, [Fe/H] −0.5 to +0.5 range are labelled `prediction` and every cell's `flags` is empty (`web/public/data/planets/population.json`). For example, the solar-twin giant share is twice Cumming et al. 2008's. The failures appear only as separate `observational constraint` conclusions, so a reader looking at one cell sees an unqualified prediction. Ground rule 6 asks for validity flags. *Fix:* attach a flag to each cell naming the failed survey checks that cover it (giant occurrence for all cells; small-planet checks for 1 M☉).

**H2. The validity flags promised for stars are not implemented.** The plan's examples `near_grid_boundary` and `outside_calibration_range` appear nowhere in the code. Interpolated stars carry no interpolation-error flag, although the leave-one-out check misses its 0.02 dex target for 243 of 2,173 trios along mass and 596 of 1,808 along [Fe/H] (up to 13.8 Gyr). `evolution.build_track` returns only ending flags. *Fix:* flag interpolated stars whose grid cell exceeded the target in the leave-one-out report, and stars within one grid step of an edge.

**H3. The type II reference radius r_m comes from a different disk model.** `population.py` uses 2004a's eq. 68, R_m = 10 exp(2t/5τ) AU (`migration.max_viscous_couple_radius_au`). 2004a derives it from angular-momentum conservation for its Σ_g ∝ a^−3/2 disk. The gas phase is now Paper VII's Σ_g ∝ r^−1 disk, for which the same argument gives R_m ∝ exp(2t/3τ). Paper VII gives no formula, only r_m ≈ 15–150 (α/10⁻³) AU (§3.5), well beyond the starting 10 AU. r_m decides the direction of type II migration (outward beyond it) and the planet-dominated rate (eq. 34). 2004a notes it matters mainly for the outer disk, but seeds reach 50 AU. *Fix:* derive R_m for the r^−1 disk with a starting value inside Paper VII's range, or vary it in the sensitivity runs and report the effect.

### Medium

**M1. Paper VII's eq. 31 is used in corrected form without a record.** As printed, f_gap = (log M_p − log M_g,vis)/(log M_g,th − log M_g,vis), which is 0 at M_g,vis and 1 at M_g,th. That would drop gas accretion from full to nothing at M_g,vis, against the paper's own statement that the taper avoids "any abrupt truncation". `ida_lin_2013.gap_factor` uses the continuous reading (1 at M_g,vis, 0 at M_g,th), which is surely the intent. *Fix:* add a Source checks row, as done for 2004a's eq. 25.

**M2. "Sub-Neptune" includes bodies smaller than Earth.** In a 1,500-system solar-twin run (seed 5), 213 of 690 sub-Neptunes are below 2 M⊕ and 50 below 1 M⊕, with envelope fractions of 2–3%. The physics follows Paper VII: once a core stops growing, M_c,hydro falls to 0 and τ_KH = 10⁹ M⁻³ yr still adds about 1% over the disk's life. But the classifier has no mass floor, so the class name implies a size these planets lack. Separately, giant-impact mergers simply add the two envelopes (`population.after_gas`); impacts strip gas in reality, and Ida & Lin 2010 does not cover it. *Fix:* a mass floor or an `envelope_on_small_core` flag; record envelope addition in mergers as a shortcut.

**M3. The Sun check's tolerance was widened after the first result.** Phase 1 re-aimed L from 1.00 ± 0.05 to 0.95–1.12 L☉ and T_eff to 5712–5872 K. The reason is documented and correct: the released [Fe/H] 0 track is not MIST's calibrated solar model (Choi et al. 2016 table 2). The result, L = 1.106 L☉ and T_eff = 5848 K, sits near both new upper limits, so the check is weaker than it reads. *Fix:* if MIST's calibrated solar model (Y 0.2612, Z 0.0150) can be run or obtained, check against it with the original tolerance.

**M4. Validation rows marked "Not run" were done.** The rows are "Data contract", "Aion Forge untouched" and "Python ports of Aion Forge models":
- `tests/test_contract.py` and `contract.test.ts` run on every `make check`;
- `PROVENANCE.md` records the before-and-after SHA-256 manifests (1,016 files, identical);
- the Chen & Kipping port is checked against its paper.

*Fix:* update the three rows.

**M5. Source checks is out of date.**
- Its opening sentence counts 57 claims (36 hold, 13 tightened, 6 wrong, 2 waiting); the table now has 67 rows: 41 confirmed, 18 refined, 6 corrected, 2 not yet checkable.
- Row "CNO dominates, and convective cores appear, above roughly 1.1–1.3 M☉" is still "Not yet checkable", but Phase 4 reported both, from the model and from MIST (Validation table).
- Row "Milestone 3's pp power law" can be closed: 1.07 × 10⁻¹² is within 9% of the analytic KWW pp rate at 1.5 × 10⁷ K and matches Carroll & Ostlie's 1.08 × 10⁻¹².

### Low

**L1. The structure solver leaves out the pp II/III correction ψ and screening** in the pp and CNO rates (both set to 1, as stated in `structure.py`). Screening raises CNO rates in the solar core by roughly 20%. The 1 M☉ gate passes regardless. The 7–9% lower pp/CNO crossover mass than MIST's is consistent with the stronger CNO noted in Phase 4, but the omission is not listed with that result.

**L2. Gas-phase core growth uses the total mass.** `population.evolve` applies τ_c,acc ∝ M^1/3 (Paper VII eq. 19, written for the core mass M_c) to core plus envelope. The effect is small, because an envelope only grows once the core is past M_c,hydro.

**L3. Unused formulas.** The population no longer calls these 2004a/2008a functions; only tests use them:
- `migration.type1_rate` and `type2_rate`;
- `growth.gap_opening_mass`, `disk_gas_mass_limit`, `no_isolation_mass` and `gas_isolation_mass`;
- `disk.sigma_gas` (r^−3/2), `temperature_k`, `aspect_ratio` and `snow_line_from_luminosity_au` (the last kept for Phase 6).

They are correct transcriptions, but `disk.sigma_gas` and `ida_lin_2013.sigma_gas` now describe different disks under the same name.

**L4. Copied rendering code that will need Python inputs.** `rendering/system/systemView.ts: eccentricAnomaly` solves Kepler's equation and `rendering/planet/rings.ts: ringIciness` maps temperature to ice. No view uses them yet; when the 3D system view arrives (Phase 6 or 7), ground rule 2 needs the positions or the iciness exported from Python, or Kepler's equation explicitly accepted as animation. *Resolved in Phase 7 (15 November 2026): Kepler's equation is accepted as animation (step 4), and `rings.ts` was deleted with the planet globes (step 5).*

**L5. Plan drift.** The reuse table names `stellarforge/imf.py` and `stellarforge/planets/mass_radius.py`. Kroupa sampling lives in `experiments.py` and the mass–radius relation in `planets/radius.py`.

**L6. Interpolation detail.** `evolution.build_track` blends age linearly rather than in log age, and log g independently of mass and radius. Both are covered by the leave-one-out log-age error; noted for completeness.

## Checked and correct

| Area | What was checked | Against |
| --- | --- | --- |
| MIST reader | primary EEP numbers and names; phase codes; streamed reading, never unpacked | Dotter 2016 table 1; Choi et al. 2016 §5.1 |
| Interpolation | equal-EEP bilinear blend in log mass and [Fe/H]; only when all four corners end alike; nearest track otherwise, labelled `substituted`; no extrapolation | build plan, ground rule 6 |
| Total lifetime | MIST white-dwarf tracks end at log L ≈ 0.2, about 1 Myr after the post-AGB point, so "total lifetime" is effectively the age at white-dwarf birth | Dotter 2016, primary EEP 10 (central Γ = 100) |
| Core collapse | proto-compact masses, fallback branches and coefficients, rapid and delayed; baryonic to gravitational mass | Fryer et al. 2012 eqs. 13–20 |
| Pair instability | 45, 65 and 135 M☉ helium cores; 40.5 M☉ black hole from f_n = 0.1 | Belczynski et al. 2016 §2 |
| White dwarfs | MIST-based initial–final relation, three segments | Cummings et al. 2018 eqs. 4–6 |
| Electron capture | 9.0–9.25 M☉ window | Poelarends et al. 2008 |
| IMF | slopes 1.3 and 2.3, break at 0.5 M☉; CDF inversion continuous at the break | Kroupa 2001 |
| Polytropes | Lane–Emden solution, P_c formula, n = 0, 1, 5 exact cases | Chandrasekhar 1939 ch. IV |
| Structure equations | four equations, central series, photosphere P = 2g/3κ, ∇_rad, ∇_ad with radiation | KWW 2012 ch. 10–13 |
| Microphysics | Kramers ff/bf coefficients; pp and CNO analytic rates with g11 and g14; LUNA scaling 1.7/3.15; μ; MIST's Y(Z) | KWW 2012; Formicola et al. 2004; Choi et al. 2016 eqs. 1–3 |
| Mixing length | U, the cubic and its z = ξ − U substitution (re-derived) | Böhm-Vitense 1958 via KWW §7.2 |
| Equation of state | Saha factors and statistical weights; Sackur–Tetrode entropy (ionisation energies cancel); ∇_ad, δ and c_P from finite differences | KWW 2012 ch. 14 |
| Opacity | R = ρ/T6³; OPAL and Ferguson tables; no extrapolation | Choi et al. 2016 §3.2.2 |
| Planet disk and growth | Σ_d, Σ_g, snow line, f_g decay, τ_c,acc, isolation mass, M_c,hydro, τ_KH, Ṁ_disk, M_g,vis, M_g,th, type I and both type II regimes, C2 = 0.1 | Ida, Lin & Nagasawa 2013 eqs. 15–34 |
| Giant impacts | crossing time, escape eccentricity (0.28 coefficient), mass split and Rayleigh mean 1, energy-conserving scatter and merger | Ida & Lin 2010 eqs. 15–20 |
| Embryo isolation mass | definition evaluated (ρ_e^1/4, 0.32 M⊕); printed eq. 25 recorded as differing | Ida & Lin 2004a eqs. 20, 25 |
| Mass–radius | 1.008 M^0.279, 0.589, −0.044; breaks at 2.04 M⊕ and 0.414 M_J; segments continuous | Chen & Kipping 2017 table 1 |
| Survey cuts | 0.3–10 M_J by M sin i, 2–2,000 d; 1.0–1.7 and 1.7–4.0 R⊕ at 10–100 d; published numbers | Cumming et al. 2008; Johnson et al. 2010; Fischer & Valenti 2005; Petigura et al. 2018 |
| Exports | survey results in the files equal the Validation table; files newer than the code | `planet-surveys.json`, `population.json` |
| Ground rule 2 | views contain display scaling and unit formatting only; every shown number comes from the JSON | `web/src` |

## Not covered

- Isochrone-level behaviour and Star Builder slider snapping were not re-tested beyond `make check`.
- The Bédard et al. 2020 cooling-sequence reader was checked for format only, not against the paper.
- The C1 = 0.3 and M★² probe numbers in the plan were not re-run.
- MIST v2.5 EEP definitions remain unchecked (already a shortcut in `mist.py`).
