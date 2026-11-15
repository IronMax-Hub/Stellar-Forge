"""The remnant a single star leaves, from the last state of its MIST track.

How the track ends decides the rule (build plan, Phase 2):

- white-dwarf cooling sequence: a white dwarf of the track's final mass (MIST), compared with the
  MIST-based initial-final mass relation of Cummings et al. 2018, and cooled along the Bédard et al.
  2020 sequences;
- end of core carbon burning: core collapse by Fryer et al. 2012 ("delayed" adopted, "rapid" kept as
  the alternative), unless the helium core is in the pair-instability range of Belczynski et al.
  2016 (model M10);
- end of the main sequence: no remnant yet; any other ending: not predicted (track incomplete).

Every record assumes a single star: most massive stars interact with a companion (Sana et al.
2012), and binary channels are not covered.
"""

import tarfile
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from .evolution import CARBON_END, MS_END, NO_CO_CORE, NO_HE_CORE, Track
from .mist import CACHE

BEDARD = CACHE.parent / "bedard2020" / "AllSequences.tar.gz"

# Fryer et al. 2012, section 4: the largest neutron star in their standard model. The paper does not
# say whether it bounds the baryonic or the gravitational mass; it is applied to the baryonic mass.
NS_MAX_BARYONIC_MSUN = 2.5
NS_BINDING = 0.075             # Fryer et al. 2012 eq. 13: M_bar - M = 0.075 M^2 (Lattimer & Yahil 1989)
BH_GRAVITATIONAL_SHARE = 0.9   # Fryer et al. 2012 eq. 14: M = 0.9 M_bar for black holes
# Belczynski et al. 2016, model M10: helium cores of 45-65 M☉ pulsate and keep 45 M☉, which collapses
# to 45 (1 - f_n) = 40.5 M☉ with f_n = 0.1 lost to neutrinos (their eq. 1); 65-135 M☉ explode as
# pair-instability supernovae and leave nothing; above 135 M☉ the star collapses directly. Heger &
# Woosley 2002 give 64-133 M☉ for the explosions.
PPSN_HE_CORE_MSUN = 45.0
PISN_HE_CORE_MSUN = 65.0
DIRECT_COLLAPSE_HE_CORE_MSUN = 135.0
PPSN_BH_MSUN = 40.5
# Poelarends et al. 2008, fiducial model: electron-capture supernovae for initial masses 9.0-9.25 M☉.
ECSN_WINDOW_MSUN = (9.0, 9.25)
# Inside the measured 10-13 km (Özel & Freire 2016; Riley et al. 2019; Miller et al. 2019).
NS_RADIUS_KM = 12.0
# Schwarzschild radius 2GM/c^2 per solar mass, from the nominal GM☉ = 1.3271244e20 m^3 s^-2
# (IAU 2015 B3; Prša et al. 2016) and c = 299,792,458 m/s.
SCHWARZSCHILD_KM_PER_MSUN = 2 * 1.3271244e20 / 299_792_458.0**2 / 1e3
L_SUN_ERG_S = 3.828e33         # nominal solar luminosity (IAU 2015 B3; Prša et al. 2016)
# Cummings et al. 2018, MIST-based initial-final mass relation (eqs. 4-6): (from, to, slope, intercept)
CUMMINGS_MIST_IFMR = ((0.83, 2.85, 0.080, 0.489), (2.85, 3.60, 0.187, 0.184),
                      (3.60, 7.20, 0.107, 0.471))
CUMMINGS_SCATTER_MSUN = 0.06
# Cummings et al. 2018 (fig. 5, section 6): observed white dwarfs from higher-mass progenitors are
# ~0.1 M☉ heavier than MIST's theoretical relation (Choi et al. 2016); the two agree at low masses.
CUMMINGS_MODEL_OFFSET_MSUN = 0.1
CUMMINGS_MODELS_AGREE_BELOW_MSUN = 2.0
COOLING_POINTS = 120


@dataclass
class Remnant:
    type: str                 # white dwarf, neutron star, black hole, none, not yet, not predicted
    mass_msun: float | None
    radius_km: float | None
    provenance: str
    prescription: str
    how: str                  # how it formed, in a sentence
    # The other prescription's answer: {prescription, type, mass_msun, radius_km, how, provenance}
    alternative: dict
    final_mass_msun: float
    he_core_mass_msun: float
    co_core_mass_msun: float      # NaN where MIST gives no core mass
    flags: list[str] = field(default_factory=list)
    cooling: dict | None = None   # white dwarfs: cooling_age_yr, log_l_lsun, log_teff_k, radius_km

    def as_dict(self) -> dict:
        return asdict(self)


def fryer_baryonic_mass(m_final: float, m_co: float, delayed: bool) -> tuple[float, float]:
    """Fryer et al. 2012 eqs. 15-20: the remnant's baryonic mass and the fallback share f_fb."""
    if delayed:
        m_proto = 1.2 if m_co < 3.5 else 1.3 if m_co < 6.0 else 1.4 if m_co < 11.0 else 1.6
        if m_co < 2.5:
            return m_proto + 0.2, 0.0
        if m_co < 3.5:
            return m_proto + 0.5 * m_co - 1.05, 0.0
        a = 0.133 - 0.093 / (m_final - m_proto)
        f_fb = a * m_co - 11 * a + 1 if m_co < 11.0 else 1.0
    else:
        m_proto = 1.0
        if m_co < 2.5:
            return m_proto + 0.2, 0.0
        if m_co < 6.0:
            return m_proto + 0.286 * m_co - 0.514, 0.0
        a = 0.25 - 1.275 / (m_final - m_proto)
        f_fb = 1.0 if m_co < 7.0 or m_co >= 11.0 else a * m_co - 11 * a + 1
    return m_proto + f_fb * (m_final - m_proto), f_fb


def compact_object(m_baryonic: float) -> tuple[str, float]:
    """Neutron star or black hole, and its gravitational mass (Fryer et al. 2012 eqs. 13-14)."""
    if m_baryonic < NS_MAX_BARYONIC_MSUN:
        # Solve M_bar = M + 0.075 M^2 for M
        return "neutron star", (np.sqrt(1 + 4 * NS_BINDING * m_baryonic) - 1) / (2 * NS_BINDING)
    return "black hole", BH_GRAVITATIONAL_SHARE * m_baryonic


def core_collapse(m_final: float, m_he: float, m_co: float, delayed: bool) -> tuple[str, float | None, str]:
    """(type, gravitational mass, how) for a star that ends at carbon burning."""
    if m_he >= DIRECT_COLLAPSE_HE_CORE_MSUN:
        return ("black hole", BH_GRAVITATIONAL_SHARE * m_final,
                ("Its helium core is too massive for a pair-instability explosion to unbind it, "
                 "so the whole star collapses into a black hole."))
    if m_he >= PISN_HE_CORE_MSUN:
        return ("none", None,
                ("Its helium core is in the pair-instability range: the core collapses, ignites "
                 "explosively and the star is destroyed, leaving nothing behind."))
    if m_he >= PPSN_HE_CORE_MSUN:
        return ("black hole", PPSN_BH_MSUN,
                ("Its helium core is in the pulsational pair-instability range: pulses shed "
                 "everything above 45 M☉, and the rest collapses into a black hole."))
    kind, mass = compact_object(fryer_baryonic_mass(m_final, m_co, delayed)[0])
    how = ("The iron core collapses and a supernova explodes; " + (
        "the material that falls back keeps the remnant below the neutron-star limit."
        if kind == "neutron star" else
        "so much material falls back that the remnant becomes a black hole."))
    return kind, float(mass), how


def cummings_ifmr(initial_mass_msun: float) -> float | None:
    for lo, hi, slope, intercept in CUMMINGS_MIST_IFMR:
        if lo <= initial_mass_msun <= hi:
            return slope * initial_mass_msun + intercept
    return None


@lru_cache(maxsize=1)
def bedard_sequences(path: Path = BEDARD) -> dict[float, np.ndarray]:
    """Thick-hydrogen (DA) cooling sequences by white-dwarf mass, read in place from the archive.
    Columns: model, Teff, log g, R (cm), cooling age (yr), L (erg/s), then central and composition
    values (Bédard et al. 2020; www.astro.umontreal.ca/~bergeron/CoolingModels)."""
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; run `make data`")
    out = {}
    with tarfile.open(path) as tar:
        for member in tar:
            if member.name.endswith("_thick.txt"):
                lines = tar.extractfile(member).read().decode("ascii").splitlines()
                values = np.array(" ".join(lines[5:]).split(), dtype=float)
                if values.size % 16:
                    raise ValueError(f"{member.name}: not 16 values per model")
                out[int(member.name[4:7]) / 100] = values.reshape(-1, 16)
    return dict(sorted(out.items()))


def cooling_track(mass_msun: float) -> tuple[dict | None, list[str]]:
    """The white dwarf's cooling, blended linearly in mass between the two nearest Bédard
    sequences at equal cooling age; None outside their 0.2-1.3 M☉."""
    seqs = bedard_sequences()
    masses = np.array(list(seqs))
    if not masses[0] <= mass_msun <= masses[-1]:
        return None, ["outside_cooling_sequences: no Bédard et al. 2020 track for this mass"]
    hi = int(np.clip(np.searchsorted(masses, mass_msun), 1, len(masses) - 1))
    lo = hi - 1
    w = (mass_msun - masses[lo]) / (masses[hi] - masses[lo])
    a, b = seqs[masses[lo]], seqs[masses[hi]]
    ages = np.geomspace(max(a[1, 4], b[1, 4]), min(a[-1, 4], b[-1, 4]), COOLING_POINTS)

    def at(col, log=False):
        f = (lambda s: np.interp(np.log10(ages), np.log10(s[1:, 4]), np.log10(s[1:, col]))) if log \
            else (lambda s: np.interp(np.log10(ages), np.log10(s[1:, 4]), s[1:, col]))
        return (1 - w) * f(a) + w * f(b)

    cooling = {
        "cooling_age_yr": ages.tolist(),
        "log_l_lsun": (at(5, log=True) - np.log10(L_SUN_ERG_S)).tolist(),
        "log_teff_k": at(1, log=True).tolist(),
        "radius_km": (10 ** at(3, log=True) / 1e5).tolist(),
    }
    return cooling, []


def remnant(track: Track, initial_mass_msun: float) -> Remnant:
    """The remnant of a star whose MIST track (from evolution.build_track) is `track`."""
    v = track.values
    m_final, m_he, m_co = (float(v[k][-1]) for k in ("mass_msun", "he_core_mass_msun",
                                                     "c_core_mass_msun"))
    # MIST reports a missing core mass as 0; NaN keeps it from being read as a real zero
    m_co = float("nan") if track.ending == NO_CO_CORE else m_co
    m_he = float("nan") if track.ending == NO_HE_CORE else m_he
    base = {"final_mass_msun": m_final, "he_core_mass_msun": m_he, "co_core_mass_msun": m_co,
            "flags": ["single_star_assumed", *track.flags]}

    def same(kind: str) -> dict:
        """No alternative prescription applies: the alternative is the same outcome, without a mass."""
        return {"prescription": "no alternative", "type": kind, "mass_msun": None,
                "radius_km": None, "how": "No alternative prescription applies to this star.",
                "provenance": "derived"}

    def compact_radius_km(kind: str, mass: float | None) -> float | None:
        return (NS_RADIUS_KM if kind == "neutron star" else
                SCHWARZSCHILD_KM_PER_MSUN * mass if kind == "black hole" else None)

    if track.ending == "white-dwarf cooling sequence":
        cooling, flags = cooling_track(m_final)
        ifmr = cummings_ifmr(initial_mass_msun)
        return Remnant(
            type="white dwarf", mass_msun=m_final,
            radius_km=cooling["radius_km"][-1] if cooling else None,
            provenance=track.provenance, prescription="MIST final mass",
            how="The star sheds its envelope on the asymptotic giant branch; its exposed core "
                "cools as a white dwarf.",
            # No radius: the cooling sequence is computed for the MIST mass only
            alternative={"prescription": "Cummings et al. 2018, MIST-based relation",
                         "type": "white dwarf", "mass_msun": ifmr, "radius_km": None,
                         "how": "The same white dwarf, with its mass from Cummings et al.'s "
                                "initial-final mass relation instead of the MIST track's final "
                                "mass.",
                         "provenance": "predicted"} if ifmr else same("white dwarf"),
            cooling=cooling, **{**base, "flags": base["flags"] + flags})

    # Above 45 M☉ of helium core the pair-instability rules decide, without the CO core
    if track.ending == CARBON_END or (track.ending == NO_CO_CORE and m_he >= PPSN_HE_CORE_MSUN):
        kind, mass, how = core_collapse(m_final, m_he, m_co, delayed=True)
        alt_kind, alt_mass, alt_how = core_collapse(m_final, m_he, m_co, delayed=False)
        flags = ["final_state_at_end_of_carbon_burning"]
        if ECSN_WINDOW_MSUN[0] <= initial_mass_msun <= ECSN_WINDOW_MSUN[1]:
            flags.append("ecsn_window: may form a neutron star by electron capture instead "
                         "(Poelarends et al. 2008)")
        return Remnant(
            type=kind, mass_msun=mass,
            radius_km=compact_radius_km(kind, mass),
            provenance="predicted", prescription="Fryer et al. 2012 delayed; Belczynski et al. "
            "2016 pair instability", how=how,
            alternative={"prescription": "Fryer et al. 2012 rapid; Belczynski et al. 2016 pair "
                         "instability", "type": alt_kind, "mass_msun": alt_mass,
                         "radius_km": compact_radius_km(alt_kind, alt_mass), "how": alt_how,
                         "provenance": "predicted"},
            **{**base, "flags": base["flags"] + flags})

    if track.ending == MS_END:
        return Remnant(type="not yet", mass_msun=None, radius_km=None, provenance="derived",
                       prescription="none", how="Still on the main sequence where its MIST "
                       "track ends; it has not reached the end of its life.",
                       alternative=same("not yet"), **base)
    how = (f"Its MIST track reaches the {CARBON_END}, but MIST gives no "
           f"{'CO-core' if track.ending == NO_CO_CORE else 'helium-core'} mass there, which the "
           "remnant rules need, so no remnant is predicted."
           if track.ending.startswith(CARBON_END) else
           f"Its MIST track stops at {track.ending}, before a final phase, so no remnant is "
           "predicted.")
    return Remnant(type="not predicted", mass_msun=None, radius_km=None, provenance="derived",
                   prescription="none", how=how, alternative=same("not predicted"), **base)
