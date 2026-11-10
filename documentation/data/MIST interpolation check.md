# MIST interpolation check

Written by `python -m stellarforge.evolution check`; do not edit by hand. Each interior MIST v1.2 track is rebuilt from its two neighbours (along mass in log mass, or along [Fe/H]) at equal EEP, and compared on the main sequence (EEP 202–454). Only trios whose tracks end at the same primary EEP are used, as in `evolution.py`. Leaving a track out doubles the grid step, so these errors overstate those of the real interpolation.

Target (build plan, Validation): main-sequence errors under 0.02 dex in log L and log Teff.
Each track's error is its largest along the main sequence; the tables give the spread of
those over all tracks, for the whole main sequence and for the part up to 13.8 Gyr (the
lowest masses end their main sequence long after that).

| Axis | Part of the main sequence | Tracks | log L: median | 95th percentile | worst | log Teff: median | 95th percentile | worst | Tracks over 0.02 dex |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mass | all of it | 2259 | 0.0044 | 0.0487 | 0.8766 | 0.0011 | 0.0412 | 0.4915 | 367 |
| mass | up to 13.8 Gyr | 2259 | 0.0041 | 0.0441 | 0.1783 | 0.0010 | 0.0337 | 0.4915 | 308 |
| feh | all of it | 1914 | 0.0129 | 0.0909 | 0.8533 | 0.0041 | 0.0463 | 0.2278 | 738 |
| feh | up to 13.8 Gyr | 1914 | 0.0119 | 0.0818 | 0.2193 | 0.0039 | 0.0411 | 0.2278 | 682 |

Worst ten along mass, up to 13.8 Gyr:

| Mass (M☉) | [Fe/H] | log L error | log Teff error |
| --- | --- | --- | --- |
| 40 | +0.50 | 0.0580 | 0.4915 |
| 80 | +0.00 | 0.0490 | 0.3191 |
| 38 | +0.50 | 0.0328 | 0.2821 |
| 80 | -0.50 | 0.0996 | 0.2624 |
| 85 | +0.00 | 0.0150 | 0.2510 |
| 85 | -0.50 | 0.0757 | 0.2480 |
| 175 | -1.00 | 0.0646 | 0.2181 |
| 80 | -0.75 | 0.0641 | 0.1974 |
| 85 | -0.75 | 0.0455 | 0.1843 |
| 150 | -0.50 | 0.1783 | 0.1038 |

Worst ten along feh, up to 13.8 Gyr:

| Mass (M☉) | [Fe/H] | log L error | log Teff error |
| --- | --- | --- | --- |
| 80 | +0.00 | 0.0314 | 0.2278 |
| 65 | +0.25 | 0.1049 | 0.2198 |
| 38 | +0.25 | 0.0442 | 0.2194 |
| 90 | +0.00 | 0.2193 | 0.0524 |
| 80 | +0.25 | 0.1831 | 0.1681 |
| 145 | -0.25 | 0.1666 | 0.0415 |
| 38 | -2.00 | 0.1623 | 0.1165 |
| 75 | +0.25 | 0.1609 | 0.1362 |
| 70 | +0.25 | 0.1589 | 0.1086 |
| 32 | -2.00 | 0.1494 | 0.0937 |
