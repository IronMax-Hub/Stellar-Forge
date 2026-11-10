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
