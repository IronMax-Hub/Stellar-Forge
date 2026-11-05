# Source checks

Checked on 6 November 2026 · companion to [Stellar-Forge Build Plan](Stellar-Forge%20Build%20Plan.md)

All 56 references in the plan match their published records, and 50 claims from the plan and the outside review were checked against the papers, the MIST website or a recomputation. 32 hold as written, 11 needed tightening, 6 were wrong, and 1 waits for Phase 4 data. The plan now uses the corrected statements.

These checks confirm what each source says. They do not show that a model suits Stellar-Forge; numerical tests and scientific validation still happen in each phase.

## Claims

Links in the "Checked against" column open the local copy in `references/papers/` where one was downloaded.

| Area | Claim in the plan or review | Checked against | What the source says | Verdict |
| --- | --- | --- | --- | --- |
| MIST | MIST v1.2 follows stars from 0.1 to 300 M☉ and [Fe/H] −4.0 to +0.5 | [Choi et al. 2016](references/papers/Choi2016_arXiv-1604.08592.pdf); MIST website | Masses hold. Only [Fe/H] −2.0 to +0.5 is evolved to the end; from −4.0 to −2.5 tracks stop after core helium burning | **Corrected** |
| MIST | Very low-mass stars may not finish within a track's final age | [Choi et al. 2016](references/papers/Choi2016_arXiv-1604.08592.pdf) | Stars of 0.7 M☉ and below are stopped at the end of the main sequence, which takes over 35 Gyr at 0.7 M☉ | **Corrected** |
| MIST | 15 metallicities, about 1.5 GB for the rotating set | [MIST model grids page](references/web/MIST_model_grids.html); download-size checks | 15 archives of 76–107 MB as MIST lists them, about 1.5 GB in total | Confirmed |
| MIST | Rotating tracks (v/vcrit = 0.4) are MIST's default | [Choi et al. 2016](references/papers/Choi2016_arXiv-1604.08592.pdf) | Rotation at v/vcrit = 0.4 is the default; a non-rotating set is also released | Confirmed |
| MIST | v1.2 is the release to use | [MIST home page](references/web/MIST_index.html); [MIST references page](references/web/MIST_references.html) | MIST v2.5 was released on 24 Feb 2026 (Dotter et al. 2026, in press): GS98 abundances, [Fe/H] −4.0 to +0.5 in 0.25 dex steps, five [α/Fe] values | **Corrected** |
| MIST | EEP means equivalent evolutionary point (plan and review) | [Dotter 2016](references/papers/Dotter2016_arXiv-1601.05144.pdf) | EEP means equivalent evolutionary phase: a set of points found on every track | Refined |
| MIST | MIST reproduces the Sun at 4.57 Gyr | [Choi et al. 2016](references/papers/Choi2016_arXiv-1604.08592.pdf) | The solar model is fitted at 4.57 Gyr to luminosity, radius, surface composition, convection-zone depth and sound speed | Confirmed |
| MIST | MIST sets helium from metallicity | [Choi et al. 2016](references/papers/Choi2016_arXiv-1604.08592.pdf) | Y = 0.249 + 1.5 Z, anchored to protosolar Y = 0.2703 and Z = 0.0142 | Confirmed |
| Sun | Effective temperature 5772 K | [NASA Sun fact sheet](references/web/NASA_Sun_fact_sheet.html) (IAU 2015 nominal value) | 5772 K | Confirmed |
| Sun | Full solar models give a central temperature near 1.57 × 10⁷ K | [NASA Sun fact sheet](references/web/NASA_Sun_fact_sheet.html) | 1.571 × 10⁷ K | Confirmed |
| Remnants | White-dwarf masses follow Cummings et al. 2018 | [Cummings et al. 2018](references/papers/Cummings2018_arXiv-1809.01673.pdf) | Relation from 0.85 to 7.5 M☉, scatter 0.06 M☉; a MIST-based fit gives 0.080 Mi + 0.489 M☉ for 0.83–2.85 M☉ | Confirmed |
| Remnants | Electron-capture supernovae in a narrow window near 8–10 M☉ | [Poelarends et al. 2008](references/papers/Poelarends2008_arXiv-0705.4643.pdf) | 9.0–9.25 M☉ in their fiducial model, inside a super-AGB range of 7.5–9.25 M☉ | Refined |
| Remnants | Fryer's rapid and delayed prescriptions use carbon–oxygen core mass and final mass | [Fryer et al. 2012](references/papers/Fryer2012_arXiv-1110.1726.pdf) | Fallback is set by CO-core thresholds; their standard maximum neutron-star mass is 2.5 M☉ | Confirmed |
| Remnants | Neutron-star masses span 1.1–2.0 M☉, citing Fryer et al. 2012 | Özel & Freire 2016; [Fryer et al. 2012](references/papers/Fryer2012_arXiv-1110.1726.pdf) | Measured masses reach about 2.0 M☉; Fryer's 2.5 M☉ is a dividing convention, not a measured range | **Corrected** |
| Remnants | Pair-instability supernovae for helium cores of about 65–130 M☉, direct collapse above | Heger & Woosley 2002 | Helium cores of 64–133 M☉ (stars of about 140–260 M☉) explode; above 133 M☉ a black hole forms | Confirmed |
| Remnants | Pulsations shed mass below the pair-instability range | Heger & Woosley 2002; [Woosley 2017](references/papers/Woosley2017_arXiv-1608.08939.pdf); [Belczynski et al. 2016](references/papers/Belczynski2016_arXiv-1607.03116.pdf) | Pulsations for helium cores of about 40–63 M☉ (30–64 M☉ in Woosley's bare cores); Belczynski adopt 45–65 M☉, leaving a 40.5 M☉ black hole | Confirmed |
| Remnants | The gap appears only at low metallicity, citing Farmer et al. 2019 | [Farmer et al. 2019](references/papers/Farmer2019_arXiv-1910.12874.pdf) | The gap's lower edge sits at 45 M☉ (40–56 M☉ with reaction-rate uncertainty) and barely moves with metallicity; which stars reach it depends on their winds | **Corrected** |
| Remnants | 12 km is a typical measured neutron-star radius | Özel & Freire 2016; Riley et al. 2019; Miller et al. 2019 | X-ray estimates give 10–11.5 km; NICER gives 12.7 km and about 13 km | Refined |
| Remnants | White-dwarf cooling from Bédard et al. 2020 | Bédard et al. 2020 | The paper presents new cooling tracks for hot white dwarfs | Confirmed |
| Remnants | Pulsar kicks follow a Maxwellian with σ = 265 km/s | Hobbs et al. 2005 | Maxwellian with one-dimensional σ = 265 km/s | Confirmed |
| Structure | Lane–Emden constants for n = 1.5 and n = 3 | Recomputed with SciPy ([script](references/scripts/numeric_checks.py)) | ξ₁ = 3.65375 and ρc/ρ̄ = 5.99070; ξ₁ = 6.89685 and ρc/ρ̄ = 54.1825 | Confirmed |
| Structure | The n = 3 polytrope gives the Sun a central temperature near 1.2 × 10⁷ K | Recomputed (μ = 0.617, ideal gas) | 1.21 × 10⁷ K | Confirmed |
| Structure | CNO dominates, and convective cores appear, above roughly 1.1–1.3 M☉ | Not checked: textbook value | Phase 4 checks it against MIST's pp, CNO and convective-core columns | Not yet checkable |
| Planet formation | Σd = 10 fd ηice (a/1 AU)^−3/2 g cm⁻² | [Ida & Lin 2004a](references/papers/IdaLin2004a_arXiv-astro-ph_0312144.pdf), eq. 11 | Same form | Confirmed |
| Planet formation | fd = fg × 10^[Fe/H] | [Ida & Lin 2004b](references/papers/IdaLin2004b_arXiv-astro-ph_0408019.pdf) | Same assumption | Confirmed |
| Planet formation | Ice boost 4.2 beyond 2.7 (M★/M☉)² AU | [Ida & Lin 2004a](references/papers/IdaLin2004a_arXiv-astro-ph_0312144.pdf), eq. 15; [2005](references/papers/IdaLin2005_arXiv-astro-ph_0502566.pdf), eqs. 4 and 17 | ηice = 4.2; aice = 2.7 (M★/M☉)² AU, derived from 2.7 (L★/L☉)^1/2 AU | Confirmed |
| Planet formation | The disk-mass factor fg is drawn log-normally | [Ida & Lin 2004a](references/papers/IdaLin2004a_arXiv-astro-ph_0312144.pdf), [2004b](references/papers/IdaLin2004b_arXiv-astro-ph_0408019.pdf) | log₁₀ fg is Gaussian with σ = 1, centred at 0 (paper II) or 0.25 (paper I), cut off at fg = 30 | Refined |
| Planet formation | Heavier stars get heavier disks | [Ida & Lin 2005](references/papers/IdaLin2005_arXiv-astro-ph_0502566.pdf); Andrews et al. 2013 | Ida & Lin's standard case scales disk mass as M★²; Andrews et al. measure a roughly linear scaling, disks at 0.2–0.6% of the star | Refined |
| Planet formation | Gas disks last 1–10 Myr | [Ida & Lin 2004a](references/papers/IdaLin2004a_arXiv-astro-ph_0312144.pdf); Mamajek 2009 | Gas depletes over 10⁶–10⁷ yr; the disk fraction decays with an e-folding time of about 2.5 Myr | Confirmed |
| Planet formation | Embryos sit about 10 mutual Hill radii apart | [Ida & Lin 2004a](references/papers/IdaLin2004a_arXiv-astro-ph_0312144.pdf), citing Kokubo & Ida 1998 | Feeding zones are about 10 Hill radii wide during oligarchic growth | Confirmed |
| Planet formation | Runaway gas capture starts near 10 M⊕ | Ikoma et al. 2000; [Ida & Lin 2004a](references/papers/IdaLin2004a_arXiv-astro-ph_0312144.pdf), eq. 28 | Critical core mass of 5–20 M⊕, about 10 M⊕ scaled by accretion rate and opacity | Refined |
| Planet formation | Type I migration is damped by a factor C1 | [Ida & Lin 2008a](references/papers/IdaLin2008a_arXiv-0802.1114.pdf) | C1 explored from 0 to 1; 0.03–0.1 reproduces the observed mass–distance distribution | Refined |
| Planet formation | Rocky embryos merge after the gas is gone | Ida & Lin 2010 | Orbit crossing, scattering and giant impacts after gas depletion build close-in super-Earths | Confirmed |
| Planet formation | Rocky worlds give way to Neptunian ones near 2 M⊕ | [Chen & Kipping 2017](references/papers/ChenKipping2017_arXiv-1603.08614.pdf) | 2.0 (+0.7/−0.6) M⊕; Neptunian to Jovian at 0.414 Jupiter masses | Confirmed |
| Planet statistics | Giant planets scale as 10^(2[Fe/H]) | Fischer & Valenti 2005 | Formation probability rises with the square of the number of metal atoms | Confirmed |
| Planet statistics | Giant planets scale as M★ × 10^(1.2[Fe/H]) | Johnson et al. 2010 | Same scalings; 3% around 0.5 M☉ stars to 14% around 2 M☉ stars at solar metallicity | Confirmed |
| Planet statistics | About 10% of solar twins have a giant planet | Cumming et al. 2008 | 10.5% for 0.3–10 Jupiter masses and periods of 2–2,000 days | Confirmed |
| Planet statistics | Small planets depend only weakly on metallicity | Petigura et al. 2018; Buchhave et al. 2012 | Warm super-Earths (1.0–1.7 R⊕, 10–100 days) stay at about 20 per 100 stars from [Fe/H] −0.4 to +0.4; hot planets and sub-Neptunes rise with metallicity | Refined |
| Planet fates | Habitable-zone edges for 2,600–7,200 K stars | [Kopparapu et al. 2013](references/papers/Kopparapu2013_arXiv-1301.6674.pdf) | Valid for 2,600–7,200 K; for the Sun, water loss at 0.99 AU, runaway greenhouse at 0.97 AU, maximum greenhouse at 1.70 AU | Confirmed |
| Planet fates | Earth leaves the habitable zone within about 1 Gyr | [Kopparapu et al. 2013](references/papers/Kopparapu2013_arXiv-1301.6674.pdf) with Gough 1981's luminosity law (recomputed) | The inner edge reaches 1 AU after about 0.16 Gyr (water loss) to 0.56 Gyr (runaway greenhouse) | Refined |
| Planet fates | Orbits widen as the star loses mass, with orbit size × star mass constant | Veras et al. 2011; Schröder & Connon Smith 2008 | The slow-loss regime keeps eccentricity; Earth's orbit grows in inverse proportion to the Sun's remaining mass | Confirmed |
| Planet fates | Solar System: Earth near the edge; Mars and beyond survive on orbits widened about 1.8× | Schröder & Connon Smith 2008; Mustill & Villaver 2012; [Cummings et al. 2018](references/papers/Cummings2018_arXiv-1809.01673.pdf) | Earth is engulfed at the red-giant tip, and survival needs about 1.15 AU today. Terrestrial planets inside about 1.5 AU of a 1 M☉ star are at risk on the AGB, so Mars is borderline. Final widening is about 1.76× | **Corrected** |
| Planet fates | Giant stars swallow close planets through tides | Villaver & Livio 2009; Mustill & Villaver 2012 | Tides pull close planets in, more so for heavy planets and light stars; Jovian planets out to about 3 AU around a 1 M☉ star | Confirmed |
| Planet fates | Losing over half the mass at once unbinds planets | Energy argument; Hills 1983 | True for circular orbits; eccentric orbits can survive if the explosion happens near apastron | Refined |
| Planet fates | XUV saturation at 10^−3.13 of the star's light, decaying with exponent −1.23 (Aion Forge's model) | [Wright et al. 2011](references/papers/Wright2011_arXiv-1109.4634.pdf); [Ribas et al. 2005](references/papers/Ribas2005_arXiv-astro-ph_0412253.pdf) | −3.13 is the X-ray-only saturation level; −1.23 is the 1–1,200 Å decay for Sun-like stars, F = 29.7 τ^−1.23 erg s⁻¹ cm⁻² at 1 AU | Refined |
| Planet fates | The radius valley | Fulton et al. 2017; Owen & Wu 2017 | A gap at 1.5–2.0 R⊕ between peaks at 1.3 and 2.6 R⊕, explained by envelope evaporation | Confirmed |
| Planet fates | The cosmic shoreline | Zahnle & Catling 2017 | Planets with and without atmospheres split by insolation against escape velocity | Confirmed |
| Populations | IMF slopes 1.3 and 2.3; about 0.7% of stars born above 8 M☉ | [Kroupa 2001](references/papers/Kroupa2001_arXiv-astro-ph_0009005.pdf); recomputed | α = 1.3 for 0.08–0.5 M☉ and 2.3 above; 0.71% above 8 M☉ for 0.1–100 M☉, about 11 such stars per 1,000 M☉ formed | Confirmed |
| Populations | Most massive stars have companions | Sana et al. 2012 | Over half of O stars are in binaries, and most of those will interact | Confirmed |
| Review | Binary interaction, rotation, mass loss and mixing can change outcomes | Sana et al. 2012; Heger et al. 2003; [Farmer et al. 2019](references/papers/Farmer2019_arXiv-1910.12874.pdf) | Supported: binaries dominate massive-star evolution, winds set fates by metallicity, and the gap edge shifts with reaction rates | Confirmed |

## How the checks were done

- **References:** each was matched by journal, volume, page and year through Crossref; the three without DOIs (Chandrasekhar 1939, Zahn 1977, Verbunt & Phinney 1995) matched in OpenAlex. Metadata and retrieved abstracts are in `references/metadata/crossref_and_abstracts.json`.
- **Claims:** abstracts came from Semantic Scholar and OpenAlex; full texts of 17 papers came from arXiv (`references/papers/`, with plain-text extracts in `references/papers/text/`); MIST facts came from its website (`references/web/`).
- **Numbers:** Lane–Emden constants, the Eddington temperature, the IMF share and the habitable-zone timing were recomputed with SciPy (`references/scripts/numeric_checks.py`).
- **Reproducing:** `references/scripts/` holds the lookup and search scripts used; run them with `python3 -I` and an output folder outside `references/`.
