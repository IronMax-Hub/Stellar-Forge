# Phase 6 physics gaps: plan

15 November 2026 · companion to [Stellar-Forge Build Plan](Stellar-Forge%20Build%20Plan.md), Phase 6

Phase 6 was built on 14 November 2026 with four physical effects left out. This document says what each one is, why it matters, how to add it from published sources, and how to check it. The work is split into two phase-lets, now in the build plan:

- **Phase 6.1 — Eccentric orbits and drag near the giant**: items 1 and 2, both part of how an orbit evolves around a giant star. 3–4 days.
- **Phase 6.2 — After the giant: hot remnant ultraviolet and core-collapse survival**: items 3 and 4, both about what happens once the star stops being a giant. 2–3 days.

Phase 6.1 comes first: it changes the most planets and may change the Solar System result for Mars. The 3D system view, the fifth item left out of Phase 6, is display only and stays with Phase 7.

## What each gap does to the results today

| Gap | Planets affected | Direction of the error | Changes a fate? |
| --- | --- | --- | --- |
| 1. Circular orbits only | every planet near the giant's maximum radius | survival too optimistic: the pericentre comes closer than a, and tides are stronger there | yes, near the edge (Mars is one) |
| 2. No drag outside the photosphere | planets within a few hundredths of an AU of the giant's surface | orbit decays a little too slowly | rarely; Schröder & Connon Smith find it small next to tides |
| 3. No ultraviolet from the hot post-AGB star and white dwarf | every survivor of a star that makes a white dwarf | XUV dose too low after the giant phase; envelopes and shoreline labels too optimistic | yes for envelopes and shoreline labels, not for orbits |
| 4. No neutron-star kicks; eccentric orbits not used at core collapse | planets of stars above about 8 M☉ | survival too optimistic | not in the current planet grid (0.2–1.5 M☉), so only in a new reference case |

## Phase 6.1 — Eccentric orbits and drag near the giant

### 1. Eccentric orbits

**What is missing.** Every orbit is a circle. Real orbits are slightly oval: a planet's closest distance to its star, the pericentre q = a(1 − e), is smaller than its average distance a.

**Why it matters.**

- A planet is engulfed when its pericentre, not its average distance, reaches the star.
- The equilibrium tide falls off as (R★/a)⁸, so it acts mostly near pericentre. Mustill & Villaver (2012) include the eccentricity terms and find that eccentric planets are engulfed from farther out.
- In the Solar System, Mercury's e = 0.206 and Mars's e = 0.093 move their pericentres in by 21% and 9%. Mars's current closest approach is 1.15 stellar radii, so a 9% shift could change its fate.

**Where the eccentricities come from.** Phase 5 already makes them. In `planets/population.py` (`after_gas`), eccentricities start Rayleigh-distributed about the Hill eccentricity, and close encounters excite pairs to the escape eccentricity (Ida & Lin 2010, Appendix steps 1, 3 and 7). The array is used and then dropped. Phase 6.1 keeps it:

- `after_gas` returns `e`, `planets()` carries it, and `export.build_planet` writes it to the `systems` block.
- The Solar System case takes the planets' measured eccentricities (NASA fact sheet).

Phase 5 has a known shortcut that matters here: only the encountering pair is scattered, not the rest of its group (Appendix step 4). That shortcut's comment says to add the rest of the group "if eccentricities or spacings matter"; they now do. Phase 6.1 either adds step 4 or records the eccentricities as a lower bound with a flag. Adding step 4 is the better choice if it fits in a day.

**Physics.**

| Process | Rule | Source |
| --- | --- | --- |
| Tides with eccentricity | ȧ and ė from Mustill & Villaver's eqs. 1–2: the e² terms in f₁ (σ₁ = n), f₂ (σ₂ = 2n) and f₃ (σ₃ = 3n), with the same fiducial η_F = 3, c_F = 1, f′ = 9/2, γ_F = 2 | Mustill & Villaver 2012; Zahn 1977 |
| Slow mass loss | a × M★ constant and e kept while Ψ = (|Ṁ★|/M★)(P/2π) stays small; the existing flag at Ψ > 0.01 stays, since Veras et al. find e changes of order 0.1 from Ψ ≈ 0.02 | Veras et al. 2011; Mustill & Villaver 2012 eq. 10 |
| Engulfment | at pericentre: a(1 − e) ≤ R★ | Mustill & Villaver 2012 |
| Habitable zone | events read the orbit-averaged distance a(1 − e²)^¼ (the distance with the same mean flux); a flag where q or Q lies outside the zone while the average is inside | flux-averaging identity; Kopparapu et al. 2013 apply to circular orbits |
| XUV dose and escape | the orbit-averaged flux ∝ 1/[a² (1 − e²)^½] | the same identity |

The tidal step can no longer use the closed-form a⁸ update, because e changes at the same time. It becomes a sub-stepped integration of the (a, e) pair inside each existing step, limited so neither changes by more than 1% per sub-step. The existing refined time grid stays.

### 2. Drag outside the photosphere

**What is missing.** A planet skimming the giant's surface moves supersonically through the extended, cool chromosphere and loses angular momentum by dynamical friction. Phase 6 counts a planet as destroyed when its orbit reaches R★, which is right once it is inside: Mustill & Villaver note that orbital energy is then lost within weeks. What is missing is the friction just outside R★.

**Physics.** Schröder & Connon Smith (2008, §4.2) give the method used for Earth:

- Drag force F_d = λ_d 4π ρ (G M_p / c_s)², from Ostriker (1999), with λ_d = 3 and c_s = 8 km/s. λ_d stands for Ostriker's I/M²; at the Mach 3–4 of a planet near 1 AU it is nearer 1, so 3 is Schröder & Connon Smith's pessimistic upper bound and is reported as such.
- Angular momentum loss dΛ/dt = −F_d a, which shrinks the orbit as a ∝ Λ².
- Chromospheric density scaled from today's Sun by surface gravity (MIST's `log_g_cgs` column): a base number density of about 10¹⁷ cm⁻³ and a scale height of about 100 km today, the density scaling with g and the scale height with 1/g.

They find a decay time of about 14 Myr at 0.03 AU above the tip-RGB Sun, longer than the tidal one. So drag only adds a little in the lowest layers. It is still part of the method they used to call Earth's fate, so including it makes the Solar System comparison like for like.

**Left out on purpose.**

- **Drag from the stellar wind.** Duncan & Lissauer (1998), as cited by Mustill & Villaver, find it shrinks orbits by about 1% over the AGB.
- **What happens after entry.** Villaver & Livio (2007) estimate that planets up to about 15 Jupiter masses evaporate inside a 1 M☉ AGB envelope, but Mustill & Villaver call that limit very uncertain. The fate stays "engulfed". An optional label for planets above that mass ("may survive as a core") is a choice for later, not part of this phase-let.

The density prescription is an order-of-magnitude estimate; Schröder & Connon Smith call density the largest source of uncertainty. It gets a `shortcut:` comment and a validity flag on every planet whose orbit decay drag changed by more than 1%.

### Phase 6.1 checks

| Kind | Check | Target | Source |
| --- | --- | --- | --- |
| Numerical | Tides with e = 0 | the eccentric equations reduce to today's circular result | Mustill & Villaver 2012 eqs. 1–2 |
| Numerical | Tides circularise | ė < 0 for every e > 0 with the fiducial parameters | Mustill & Villaver 2012 eq. 2 |
| Numerical | Slow mass loss keeps e | e unchanged to 10⁻⁶ over a mass-loss-only track | Veras et al. 2011 |
| Numerical | Drag by hand | about 14 Myr decay time at 0.03 AU above the tip-RGB Sun with their density, λ_d = 3 and c_s = 8 km/s | Schröder & Connon Smith 2008 §4.2 |
| Scientific | Innermost survivors on the AGB | Mustill & Villaver find about 2 AU (1 M☉) and 10 AU (5 M☉) for the innermost planets leaving the AGB. Compared, not required to match, because their stellar models (Vassiliadis & Wood 1993) differ from MIST | Mustill & Villaver 2012, discussion |
| Scientific | Solar System re-run | the Phase 6 reference case with measured eccentricities; Mars's fate, closest approach and deciding phase reported again | build plan, Phase 6 |
| Numerical | Phase 5 unchanged | adding `e` to the export changes no Phase 5 statistic (the array was already drawn; only its export is new) | `tests/test_planets.py` |

### Phase 6.1 changes

- **Python:**
  - `planets/population.py`: return e; optionally add Appendix step 4.
  - `planets/coevolution.py`: eccentric tides, pericentre engulfment, orbit-averaged flux, drag.
  - `export.py`: `e` on each planet.
- **Contract (schema version 11):**
  - `systems` planets gain `e`.
  - `timeline` planets gain `orbit_e` knots beside `orbit_a_au`, and the closest approach is measured at pericentre.
  - Python also exports the pericentre and apocentre at each knot, so the web draws an ellipse through two given distances and computes nothing.
- **Web:** System Timeline draws ellipses; the fates table shows e at formation and at the end.

## Phase 6.2 — After the giant: hot remnant ultraviolet and core-collapse survival

### 3. Ultraviolet from the hot post-AGB star and the white dwarf

**What is missing.** After the main sequence, `planets/xuv.py` holds the XUV at its main-sequence-end value, as Aion Forge does. That is right for cool giants, which are X-ray faint. It is wrong once the star sheds its envelope:

- The post-AGB star heats from a few thousand to over 100,000 K in MIST's own track (EEPs 1409–1710).
- The new white dwarf then cools from that temperature over billions of years.
- At those temperatures most of the light is ultraviolet.

The MIST tracks also stop at the start of the cooling sequence, so today's timelines end there.

**Why it matters.** Villaver & Livio (2007) find that, around a 1 M☉ star, gas planets below 1 Jupiter mass starting inside about 3–5 AU do not survive the hot post-AGB (planetary-nebula) phase, while planets above 2 Jupiter masses survive down to about 3 AU; Jupiter-like planets within about 5 AU of a white dwarf below 0.63 M☉ are destroyed. For lower-mass white dwarfs, that, not tides, decides whether a giant planet keeps its gas.

**Physics, mostly from code already in the repository.**

- **XUV after the main sequence:** the larger of (a) the held activity value and (b) L★ × `photospheric_share(Teff)`. The blackbody share below 100 nm is already in `planets/xuv.py`, ported from Aion Forge. This covers the post-AGB part of the MIST track with no new data.
- **After the MIST track ends:** the white-dwarf cooling sequence already used in Phase 2 continues the star. `remnants.cooling_track` gives log L, log Teff and radius against cooling age from Bédard et al. (2020). The timeline joins it to the MIST track's last point and runs to a fixed end, the age of the universe (13.8 Gyr) or a 10 Gyr cooling age, whichever comes first.
- **Planets after the join:** orbits stay fixed (no more mass loss, no tides from a white dwarf); dose, envelope escape, shoreline label and class keep being updated.
- **Habitable zone around the white dwarf:** stays undefined, since Kopparapu et al. apply only up to 7,200 K. That is said in the view, not extrapolated.

**Limits, each flagged.**

- A blackbody stands in for a white-dwarf model atmosphere below 100 nm.
- Owen & Wu's thin-envelope radius is outside its range for gas giants, so their radius falls back to Chen & Kipping, as today.
- The energy-limited rate is a rough guide at these fluxes.

### 4. Neutron-star kicks and eccentric orbits at core collapse

**What is missing.** Today's rule (Hills 1983) unbinds a circular orbit when more than half the mass is lost at once. Two refinements are missing:

- With an eccentric orbit, survival depends on where the planet is when the star explodes. With instant mass loss and no kick, it stays bound only if M_after / M_before > 1 − r / 2a, where r is its distance at that moment (energy conservation; the share of mass lost must stay below r / 2a). Near apocentre the planet moves slowly and is easier to keep, which is Hills's apastron exception.
- A newborn neutron star is kicked at hundreds of km/s. Hobbs et al. (2005) fit a Maxwellian with σ = 265 km/s, a mean of about 420 km/s, to pulsar proper motions. A kick that large unbinds almost any planet.

**Physics.**

- **Survival probability by Monte Carlo** (seeded, one RNG per planet):
  - draw where the planet is along its orbit at the explosion (uniform in mean anomaly);
  - draw the kick vector (isotropic, Maxwellian magnitude with σ = 265 km/s);
  - remove the lost mass at once;
  - the planet survives if its new orbital energy is negative.

  It reports the share that survive and, for survivors, the typical new a and e.
- **Black holes:** Fryer et al. (2012, eq. 21), already used for remnant masses, scale the Hobbs kick by (1 − f_fb), the share of the envelope that does not fall back: full kicks for little fallback, none for direct collapse. `remnants.fryer_baryonic_mass` already returns f_fb; the `Remnant` record must keep it. Where that function returns f_fb = 0 for a fixed fallback mass above 0.2 M☉ (delayed engine, CO cores of 2.5–3.5 M☉) the kick is overstated, which is flagged.

**Where it shows.** The planet grid covers only 0.2–1.5 M☉, and no such star ends in core collapse. So this enters as a new reference case, **planets around massive stars**:

- test planets of Earth and Jupiter mass at 0.5–50 AU around grid stars of 9–25 M☉ at [Fe/H] 0;
- survival probability against orbit;
- shown in the Experiments view.

The PSR B1257+12 pulsar planets (Wolszczan & Frail 1992) stay described, not modelled: they most likely formed after the explosion.

### Phase 6.2 checks

| Kind | Check | Target | Source |
| --- | --- | --- | --- |
| Numerical | The join to the cooling sequence | log L and log Teff continuous at the join to within 0.1 dex, or the gap reported | MIST v1.2; Bédard et al. 2020 |
| Numerical | Main-sequence XUV unchanged | the new rule changes no XUV value on the main sequence or red-giant branch | `planets/xuv.py` |
| Scientific | Giant planets during the hot post-AGB phase | around a 1 M☉ star, planets below 1 M_J starting inside about 3–5 AU are removed and those above 2 M_J survive down to about 3 AU. Compared, not required: energy-limited escape with a Chen & Kipping radius is outside Owen & Wu's range for giants | Villaver & Livio 2007, abstract and §6 |
| Numerical | Zero kick, eccentric orbit | the Monte Carlo survival matches the analytic rule M_after / M_before > 1 − r / 2a averaged over the orbit | Hills 1983 |
| Numerical | Kick distribution | the drawn kicks have mean 2σ√(2/π) ≈ 423 km/s | Hobbs et al. 2005 |
| Scientific | Solar System | unchanged orbits and fates; Jupiter keeps its envelope (it ends near 9.6 AU) | Mustill & Villaver 2012 |

### Phase 6.2 changes

- **Python:**
  - `planets/xuv.py`: the post-main-sequence rule.
  - `planets/coevolution.py`: the cooling-sequence extension; the supernova Monte Carlo replaces `supernova_unbinds`, which stays as its zero-kick, circular check.
  - `experiments.py`: the massive-star reference case.
- **Contract (schema version 12, or 11 if both phase-lets ship together):**
  - The `timeline` star series continues past the MIST track. A per-age `source` (`MIST` or `Bédard et al. 2020`) says where each point came from.
  - Planets gain a nullable `supernova_survival` (share of draws that stay bound).
- **Web:** the System Timeline scrubber continues into the white dwarf's cooling; the massive-star case appears in Experiments.

## Sources to check before building

Checked on 15 November 2026 (rows in `Source checks.md`):

- **Ostriker 1999** (ApJ 513, 252): refined. The force law holds; λ_d is Schröder & Connon Smith's I/M², and 3 is its pessimistic end.
- **Villaver & Livio 2007** (ApJ 661, 1192): refined. The result depends on planet mass and on the starting orbit, and covers the whole planet, not only its envelope; the check above now says so.
- **Duncan & Lissauer 1998** (Icarus 134, 303): citation confirmed; the 1% figure is checked only through Mustill & Villaver, as the paper itself was not reachable.

- **Ida & Lin 2010**, Appendix: refined (9 steps; the ones used are 1, 3 and 7). Phase 5's code follows eqs. 17–18.
- **Hills 1983**: corrected. The abstract confirms the apastron exception; the full text is not open, and the bound condition is M_after / M_before > 1 − r / 2a from energy conservation, not r / 2a as first written.
- **Black-hole natal kicks**: confirmed in Fryer et al. 2012, eq. 21 (above).

Nothing is left to check before building.

## Order and effort

1. **Phase 6.1, 3–4 days:**
   - export e from Phase 5 and give the Solar System its measured eccentricities;
   - eccentric tides and pericentre engulfment;
   - drag;
   - checks, contract and view.
2. **Phase 6.2, 2–3 days:**
   - the XUV rule;
   - the cooling-sequence extension;
   - the supernova Monte Carlo and the massive-star case;
   - checks, contract and view.

Both run inside the machine budget: Phase 6.1 adds sub-steps only near the giant's maximum radius, and the Monte Carlo needs about 10⁴ draws per planet for a handful of reference planets.

The Phase 6 Solar System widening check (1.852× against 1.76–1.84×) is a separate open decision and is not changed by either phase-let: it comes from MIST's white-dwarf mass, not from these gaps.
