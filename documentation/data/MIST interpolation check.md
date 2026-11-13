# MIST interpolation check

Written by `python -m stellarforge.evolution check`; do not edit by hand. Each interior MIST v1.2 track is rebuilt from its two neighbours (along mass in log mass, or along [Fe/H]) at equal EEP, and compared on the main sequence (EEP 202–454). Only trios whose tracks end at the same primary EEP are used, as in `evolution.py`. Leaving a track out doubles the grid step, so these errors overstate those of the real interpolation.

Target (build plan, Validation): main-sequence errors under 0.02 dex in log L and log Teff.
Each track's error is its largest along the main sequence; the tables give the spread of
those over all tracks, for the whole main sequence and for the part up to 13.8 Gyr (the
lowest masses end their main sequence long after that).

| Axis | Part of the main sequence | Tracks | log L: median | 95th percentile | worst | log Teff: median | 95th percentile | worst | Tracks over 0.02 dex |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mass | all of it | 2173 | 0.0042 | 0.0457 | 0.8766 | 0.0010 | 0.0292 | 0.4915 | 302 |
| mass | up to 13.8 Gyr | 2173 | 0.0039 | 0.0356 | 0.1783 | 0.0009 | 0.0229 | 0.4915 | 243 |
| feh | all of it | 1808 | 0.0125 | 0.0921 | 0.8533 | 0.0039 | 0.0383 | 0.2278 | 652 |
| feh | up to 13.8 Gyr | 1808 | 0.0115 | 0.0820 | 0.2193 | 0.0038 | 0.0349 | 0.2278 | 596 |

Worst ten along mass, up to 13.8 Gyr:

| Mass (M☉) | [Fe/H] | log L error | log Teff error |
| --- | --- | --- | --- |
| 40 | +0.50 | 0.0580 | 0.4915 |
| 80 | +0.00 | 0.0490 | 0.3191 |
| 38 | +0.50 | 0.0328 | 0.2821 |
| 85 | +0.00 | 0.0150 | 0.2510 |
| 150 | -0.50 | 0.1783 | 0.1038 |
| 45 | +0.50 | 0.0348 | 0.1668 |
| 85 | -0.25 | 0.1640 | 0.1384 |
| 65 | +0.50 | 0.0296 | 0.1619 |
| 175 | -0.75 | 0.0640 | 0.1588 |
| 80 | +0.25 | 0.1552 | 0.0761 |

Worst ten along feh, up to 13.8 Gyr:

| Mass (M☉) | [Fe/H] | log L error | log Teff error |
| --- | --- | --- | --- |
| 80 | +0.00 | 0.0314 | 0.2278 |
| 65 | +0.25 | 0.1049 | 0.2198 |
| 38 | +0.25 | 0.0442 | 0.2194 |
| 90 | +0.00 | 0.2193 | 0.0524 |
| 80 | +0.25 | 0.1831 | 0.1681 |
| 145 | -0.25 | 0.1666 | 0.0415 |
| 75 | +0.25 | 0.1609 | 0.1362 |
| 70 | +0.25 | 0.1589 | 0.1086 |
| 85 | -0.25 | 0.1478 | 0.0939 |
| 105 | +0.25 | 0.1443 | 0.0548 |

## Every stage and more quantities

The same rebuilds, compared over the main sequence (EEP 202–454) and after it (EEP 454 to the last EEP all three tracks reach), in dex; `log age` is the age at which each EEP, and so each phase, is reached. At the end of tracks that end finally (white dwarf or end of carbon burning), the final mass and core masses that the remnant rules use are compared as a fraction; trios where MIST gives no core mass are left out.

| Axis | Stage | Quantity | Tracks | Median | 95th percentile | Worst |
| --- | --- | --- | --- | --- | --- | --- |
| mass | main sequence | log L | 2173 | 0.0042 | 0.0457 | 0.8766 |
| mass | main sequence | log Teff | 2173 | 0.0010 | 0.0292 | 0.4915 |
| mass | main sequence | log R | 2173 | 0.0024 | 0.0518 | 0.9795 |
| mass | main sequence | log age | 2173 | 0.0067 | 0.0563 | 0.1967 |
| mass | after the main sequence | log L | 1936 | 0.1920 | 0.8597 | 3.4380 |
| mass | after the main sequence | log Teff | 1936 | 0.0438 | 0.4291 | 1.8667 |
| mass | after the main sequence | log R | 1936 | 0.1839 | 0.9111 | 4.3038 |
| mass | after the main sequence | log age | 1936 | 0.0041 | 0.0176 | 0.0485 |
| mass | end of the track | final mass | 1661 | 0.2% | 5.7% | 68.2% |
| mass | end of the track | final helium core | 1661 | 0.2% | 5.0% | 68.2% |
| mass | end of the track | final CO core | 1661 | 1.1% | 12.3% | 74.2% |
| feh | main sequence | log L | 1808 | 0.0125 | 0.0921 | 0.8533 |
| feh | main sequence | log Teff | 1808 | 0.0039 | 0.0383 | 0.2278 |
| feh | main sequence | log R | 1808 | 0.0066 | 0.0694 | 0.4717 |
| feh | main sequence | log age | 1808 | 0.0149 | 0.0745 | 0.4984 |
| feh | after the main sequence | log L | 1576 | 0.2595 | 0.9173 | 3.4138 |
| feh | after the main sequence | log Teff | 1576 | 0.0594 | 0.3969 | 1.6967 |
| feh | after the main sequence | log R | 1576 | 0.2497 | 0.8686 | 4.3673 |
| feh | after the main sequence | log age | 1576 | 0.0089 | 0.0244 | 0.0511 |
| feh | end of the track | final mass | 1443 | 0.4% | 5.8% | 58.0% |
| feh | end of the track | final helium core | 1443 | 0.4% | 4.7% | 58.0% |
| feh | end of the track | final CO core | 1443 | 1.4% | 12.6% | 64.2% |

## Storage precision

`mist.py` stores every column but age as float32. Largest difference between the stored grid and the float64 values streamed from `MIST_v1.2_feh_p0.00_afe_p0.0_vvcrit0.4_EEPS.txz`:

| Column | Largest absolute difference | Largest relative difference |
| --- | --- | --- |
| `age_yr` | 0 | 0 |
| `mass_msun` | 1.5e-05 | 6e-08 |
| `log_l_lsun` | 2.4e-07 | 5.9e-08 |
| `log_teff_k` | 2.4e-07 | 6e-08 |
| `log_r_rsun` | 1.2e-07 | 6e-08 |
| `log_g_cgs` | 4.7e-07 | 6e-08 |
| `he_core_mass_msun` | 1.9e-06 | 5.9e-08 |
| `c_core_mass_msun` | 9.5e-07 | 5.9e-08 |
| `o_core_mass_msun` | 0 | 0 |
| `center_h1` | 3e-08 | 5.9e-08 |
| `center_he4` | 3e-08 | 5.9e-08 |
| `log_center_t_k` | 4.8e-07 | 6e-08 |
| `log_center_rho_cgs` | 2.4e-07 | 5.9e-08 |
| `phase` | 0 | 0 |
