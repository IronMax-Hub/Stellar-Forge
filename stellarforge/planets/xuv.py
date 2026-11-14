"""A star's XUV (X-ray plus extreme-ultraviolet) luminosity over its life, ported from Aion Forge's
`frontend/src/simulation/star.ts` (xuvLuminosityAt and its terms; see PROVENANCE.md).

L_XUV = L_bol × (A × 10^-3.13 × activity(t) × envelope share + photospheric share), with

- the saturated level 10^-3.13 of the star's light (Wright et al. 2011; X-ray only, 0.1-2.4 keV);
- activity 1 until t_sat, then (t / t_sat)^-1.23 (Ribas et al. 2005, the 1-1,200 Å decay of
  Sun-like stars);
- t_sat from the main-sequence temperature: 0.1 Gyr at 5,200 K and above, 0.8 Gyr at 3,900 K,
  8 Gyr at 2,700 K and below, linear between (Aion Forge's choice, its decision 36);
- the activity law fading out across 6,500-7,500 K, where convective envelopes vanish (Aion
  Forge's choice, decision 37), and the blackbody's share of light below 100 nm added;
- A set so the Sun at 4.6 Gyr and 1 L☉ emits its measured 3.4 × 10⁻⁶ L☉ (Aion Forge).

Bands mix: Wright's level is X-ray only while Ribas's decay covers 1-1,200 Å; the port keeps
Aion Forge's numbers and says so. After the main sequence the XUV is held at its value at the
main sequence's end, as in Aion Forge (cool giants are X-ray faint); a white dwarf's own
ultraviolet is not included. Here L_bol(t) is the MIST track's, not Aion Forge's linear law.
"""

import numpy as np

XUV_SATURATED_SHARE = 10**-3.13
ACTIVITY_DECAY_EXPONENT = 1.23
SATURATION = {"g_k": 5200.0, "g_gyr": 0.1, "early_m_k": 3900.0, "early_m_gyr": 0.8,
              "late_m_k": 2700.0, "late_m_gyr": 8.0}
ENVELOPE_FADE_K = (6500.0, 7500.0)
SOLAR_XUV_TODAY = 3.4e-6
SOLAR_AGE_GYR = 4.6
SOLAR_TEMPERATURE_K = 5772.0
XUV_MAX_NM = 100.0
PLANCK_C2_NM_K = 1.4388e7


def saturation_time_gyr(teff_k: float) -> float:
    s = SATURATION
    if teff_k >= s["g_k"]:
        return s["g_gyr"]
    if teff_k >= s["early_m_k"]:
        return s["early_m_gyr"] + (s["g_gyr"] - s["early_m_gyr"]) * (
            (teff_k - s["early_m_k"]) / (s["g_k"] - s["early_m_k"]))
    if teff_k > s["late_m_k"]:
        return s["late_m_gyr"] + (s["early_m_gyr"] - s["late_m_gyr"]) * (
            (teff_k - s["late_m_k"]) / (s["early_m_k"] - s["late_m_k"]))
    return s["late_m_gyr"]


def activity(saturation_gyr: float, t_gyr):
    t = np.asarray(t_gyr, float)
    return np.where(t <= saturation_gyr, 1.0,
                    (np.maximum(t, saturation_gyr) / saturation_gyr) ** -ACTIVITY_DECAY_EXPONENT)


def envelope_share(teff_k: float) -> float:
    lo, hi = ENVELOPE_FADE_K
    return min(1.0, max(0.0, (hi - teff_k) / (hi - lo)))


def photospheric_share(teff_k: float) -> float:
    """A blackbody's share of its output below 100 nm (series for ∫ x³/(eˣ-1) from x₀)."""
    if teff_k <= 0:
        return 0.0
    x0 = PLANCK_C2_NM_K / (XUV_MAX_NM * teff_k)
    k = np.arange(1, 41)
    terms = np.exp(-k * x0) * (x0**3 / k + 3 * x0**2 / k**2 + 6 * x0 / k**3 + 6 / k**4)
    return float(terms.sum() * 15 / np.pi**4)


ACTIVITY_SCALE = float((SOLAR_XUV_TODAY - photospheric_share(SOLAR_TEMPERATURE_K)) / (
    XUV_SATURATED_SHARE * activity(saturation_time_gyr(SOLAR_TEMPERATURE_K), SOLAR_AGE_GYR)))


def xuv_share(teff_ms_k: float, age_yr, ms_end_yr: float | None):
    """L_XUV / L_bol at each age, for a star whose main-sequence temperature is teff_ms_k; held at
    its main-sequence-end value after ms_end_yr (None: the track never leaves the main sequence)."""
    t = np.asarray(age_yr, float)
    if ms_end_yr is not None:
        t = np.minimum(t, ms_end_yr)
    active = ACTIVITY_SCALE * XUV_SATURATED_SHARE * envelope_share(teff_ms_k)
    return active * activity(saturation_time_gyr(teff_ms_k), t / 1e9) + photospheric_share(
        teff_ms_k)
