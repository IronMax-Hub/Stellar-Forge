"""Planets through their star's life (build plan, Phase 6): every planet of one star is stepped along
the star's MIST track together, with finer steps where the star's radius, mass or age changes fast.

Per step, in this order:

1. Orbits widen as the star loses mass: a × M★ stays constant and e is kept while the loss is
   slow next to the orbit (Veras et al. 2011); a step where (|Ṁ★|/M★)(P/2π) > 0.01 is flagged as
   not slow.
2. After the main sequence, in sub-steps that change neither a nor e by more than 1% (midpoint
   rule):
   - Zahn's (1977) equilibrium tide in the convective envelope, in Mustill & Villaver's (2012)
     form with the leading eccentricity terms, eqs. 1, 2, 4 and 5:
     ȧ = -(a / 9 t_conv) K [2f₂ + e²(7/8 f₁ - 10 f₂ + 441/8 f₃)],
     ė = -(e / 36 t_conv) K [5/4 f₁ - 2 f₂ + 147/4 f₃], K = (M_env/M★) q (1 + q) (R★/a)⁸,
     f_i = 9/2 min[1, (P / i t_conv)²], t_conv = (M_env R★² / 3 L★)^1/3, with M_env = M★ - M_He-core
     and the envelope reaching R★ (their §3 approximations; fiducial η_F = 3, c_F = 1, f' = 9/2,
     γ_F = 2). The planet's own tide, which they find unimportant, is left out. On the main
     sequence the tide is left out: the approximation M_env ≈ M★ would overstate it there.
   - Drag in the chromosphere just outside R★ (Schröder & Connon Smith 2008 §4.2, after Ostriker
     1999): F_d = λ_d 4πρ (G M_p / c_s)², dΛ/dt = -F_d a, with λ_d = 3 and c_s = 8 km/s. The density
     is today's low solar chromosphere (10¹⁷ particles cm⁻³ at 100 km, scale height 100 km) with
     the density scaled by g and the heights by 1/g.
3. A planet whose pericentre a(1 - e) reaches the star's radius is engulfed (Villaver & Livio
   2009; Mustill & Villaver 2012); its closest approach in stellar radii and the deciding phase
   are kept.
4. The XUV dose (xuv.py) feeds the shoreline label (shoreline.py) and energy-limited envelope
   escape (escape.py). The two are reported side by side, never merged. Both use the orbit-averaged
   flux, ∝ 1 / [a² (1 - e²)^½].
5. The Phase 5 class rules are applied again; a change is an event.
6. The habitable zone: Kopparapu et al. 2013 (Table 3 with eq. 2-3), runaway greenhouse to maximum
   greenhouse, defined only for 2,600-7,200 K stars; outside that no event is drawn. An eccentric
   planet is placed at a(1 - e²)^¼, the distance with the same mean flux, and flagged where its
   pericentre or apocentre lies outside the zone while that distance is inside.

At the track's end survivors orbit the white dwarf; after core collapse a circular orbit is unbound
when more than half the system's mass is lost at once (Hills 1983). Neutron-star kicks (Hobbs et
al. 2005) would lower survival further and are not modelled; a bound planet carries a flag.
"""

from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise

import numpy as np

from ..evolution import CARBON_END, Track, build_track
from . import M_EARTH_PER_MSUN, escape, shoreline, xuv
from .classify import F_ENV_ENVELOPE, classify
from .radius import radius_rearth

AU_CM = escape.AU_CM
R_SUN_AU = 6.957e10 / AU_CM
MSUN_G = 1.98841e33
G_CGS = escape.G_CGS
L_SUN_ERG_S = escape.L_SUN_ERG_S
YEAR_S = escape.YEAR_S
V_ESC_EARTH_KMS = 11.186

# Kopparapu et al. 2013, Table 3: S_eff☉, a, b, c, d for S_eff = S_eff☉ + aT + bT² + cT³ + dT⁴,
# T = Teff - 5780 K (eq. 2); d = (L/L☉ / S_eff)^½ AU (eq. 3)
HZ_COEFFICIENTS = {
    "moist greenhouse": (1.0140, 8.1774e-5, 1.7063e-9, -4.3241e-12, -6.6462e-16),
    "runaway greenhouse": (1.0512, 1.3242e-4, 1.5418e-8, -7.9895e-12, -1.8328e-15),
    "maximum greenhouse": (0.3438, 5.8942e-5, 1.6558e-9, -3.0045e-12, -5.2983e-16),
}
HZ_TEFF_RANGE_K = (2600.0, 7200.0)
ETA_F, F_PRIME = 3.0, 4.5          # Mustill & Villaver 2012 fiducial values
# Schröder & Connon Smith 2008 §4.2: drag strength, chromospheric sound speed, and today's low
# solar chromosphere (Lemaire et al. 1981; Maltby et al. 1986), scaled with surface gravity
DRAG_LAMBDA, SOUND_SPEED_CM_S = 3.0, 8e5
CHROMOSPHERE_N_CM3, CHROMOSPHERE_HEIGHT_CM = 1e17, 1e7
# Mean mass per particle: 1.2 m_H turns their 2 × 10¹² cm⁻³ into their ρ ≈ 4 × 10⁻⁹ kg m⁻³
CHROMOSPHERE_PARTICLE_G = 1.2 * 1.6726e-24
G_SUN_CGS = 2.7398e4                # IAU 2015 nominal solar surface gravity
MAX_ORBIT_CHANGE = 0.01             # per tidal sub-step, relative change in a and in e
MAX_SUBSTEPS = 20000
DRAG_FLAG_SHARE = 0.01              # flag planets whose inward drift is over 1% drag
TIDES_FROM_PHASE = 2               # MIST phase codes ≥ 2: after the main sequence
ADIABATIC_LIMIT = 0.01
# Step refinement: per sub-step at most this change in log10 R★, ln age and log10 M★
MAX_DLOG_R, MAX_DLN_AGE, MAX_DLOG_M = 0.01, 0.05, 0.002
OUTPUT_SAMPLES = 120               # ages exported for the System Timeline scrubber
EARTH_DOSE_AGE_YR = 4.6e9          # the shoreline's Earth dose: MIST Sun at 1 AU to 4.6 Gyr
HZ_MIN_STAY_YR = 1e7               # a shorter stay in or out of the zone is not reported
ENVELOPE_GONE = 1e-9               # M_env / M_core below this counts as stripped
FATES = ("engulfed", "unbound", "orbits white dwarf", "orbits neutron star", "orbits black hole",
         "unresolved")
EVENT_KINDS = ("formed", "enters habitable zone", "leaves habitable zone", "crosses shoreline",
               "envelope stripped", "class changed", "engulfed", "unbound", "orbits remnant",
               "track ends")


def habitable_edge_au(limit: str, l_lsun, teff_k):
    """Distance (AU) of one Kopparapu et al. 2013 limit; NaN outside 2,600-7,200 K."""
    s0, a, b, c, d = HZ_COEFFICIENTS[limit]
    t = np.asarray(teff_k, float) - 5780.0
    s_eff = s0 + a * t + b * t**2 + c * t**3 + d * t**4
    inside = (np.asarray(teff_k) >= HZ_TEFF_RANGE_K[0]) & (np.asarray(teff_k) <= HZ_TEFF_RANGE_K[1])
    with np.errstate(invalid="ignore"):    # S_eff turns negative far outside the valid range
        return np.where(inside, np.sqrt(np.asarray(l_lsun, float) / s_eff), np.nan)


@dataclass
class StarHistory:
    track: Track
    age_yr: np.ndarray
    mass_msun: np.ndarray
    radius_au: np.ndarray
    l_lsun: np.ndarray
    teff_k: np.ndarray
    core_msun: np.ndarray
    phase: np.ndarray
    l_xuv_lsun: np.ndarray
    fluence: np.ndarray            # cumulative ∫ L_XUV dt, L☉ yr
    hz_inner_au: np.ndarray
    hz_outer_au: np.ndarray
    flags: list[str]

    def phase_name(self, i: int) -> str:
        return self.track.phase_names[int(self.phase[i])]


def star_history(track: Track) -> StarHistory:
    """The track on a refined time grid, linear in age between EEPs (as evolution.Star.at)."""
    v = track.values
    age = v["age_yr"]
    steps = np.maximum.reduce([
        np.abs(np.diff(v["log_r_rsun"])) / MAX_DLOG_R,
        np.abs(np.diff(np.log(np.maximum(age, 1.0)))) / MAX_DLN_AGE,
        np.abs(np.diff(np.log10(v["mass_msun"]))) / MAX_DLOG_M, np.ones(len(age) - 1)])
    n = np.clip(np.ceil(steps).astype(int), 1, 400)
    x = np.concatenate([i + np.arange(k) / k for i, k in enumerate(n)] + [[len(age) - 1.0]])
    eep = np.arange(len(age))

    def col(name):
        return np.interp(x, eep, v[name])

    a = col("age_yr")
    mass, l = col("mass_msun"), 10 ** col("log_l_lsun")
    teff = 10 ** col("log_teff_k")
    phase = v["phase"][np.floor(x).astype(int)]
    teff_ms = 10 ** v["log_teff_k"][min(201, len(age) - 1)]
    ms_end = float(age[453]) if len(age) > 453 else None
    l_xuv = l * xuv.xuv_share(teff_ms, a, ms_end)
    fluence = np.concatenate([[0.0], np.cumsum(0.5 * (l_xuv[1:] + l_xuv[:-1]) * np.diff(a))])
    inner = habitable_edge_au("runaway greenhouse", l, teff)
    flags = []
    if np.any(np.isnan(inner)):
        flags.append("habitable_zone_undefined_part_of_track: Teff outside Kopparapu et al.'s "
                     "2,600-7,200 K")
    return StarHistory(track, a, mass, 10 ** col("log_r_rsun") * R_SUN_AU, l, teff,
                       np.minimum(col("he_core_mass_msun"), mass), phase, l_xuv, fluence, inner,
                       habitable_edge_au("maximum greenhouse", l, teff), flags)


@lru_cache(maxsize=1)
def earth_fluence_lsun_yr() -> float:
    """One Earth dose: the MIST Sun's XUV fluence at 1 AU over its first 4.6 Gyr."""
    h = star_history(build_track(1.0, 0.0))
    return float(np.interp(EARTH_DOSE_AGE_YR, h.age_yr, h.fluence))


def supernova_unbinds(m_before_msun, m_after_msun, m_planet_msun=0.0):
    """A circular orbit is unbound when more than half the system's mass is lost at once
    (Hills 1983)."""
    total = np.asarray(m_before_msun) + m_planet_msun
    return (np.asarray(m_before_msun) - np.asarray(m_after_msun)) > 0.5 * total


def _period_s(a_au, m_total_msun):
    return 2 * np.pi * np.sqrt((a_au * AU_CM) ** 3 / (G_CGS * m_total_msun * MSUN_G))


def flux_distance_au(a_au, e):
    """The circular orbit with the same orbit-averaged flux: a (1 - e²)^¼."""
    return np.asarray(a_au) * (1 - np.asarray(e) ** 2) ** 0.25


def tide_rates_per_yr(a_au, e, m_planet_msun, m_star_msun, m_env_msun, r_star_au, l_lsun):
    """ȧ/a and ė/e (per year) from Mustill & Villaver 2012 eqs. 1-2, 4 and 5 (fiducial values)."""
    a_au, e = np.asarray(a_au, float), np.asarray(e, float)
    t_conv = (m_env_msun * MSUN_G * (r_star_au * AU_CM) ** 2 / (ETA_F * l_lsun * L_SUN_ERG_S)
              ) ** (1 / 3)
    p = _period_s(a_au, m_star_msun + m_planet_msun)
    f1, f2, f3 = (F_PRIME * np.minimum(1.0, (p / (i * t_conv)) ** 2) for i in (1, 2, 3))
    q = m_planet_msun / m_star_msun
    k = (m_env_msun / m_star_msun) * q * (1 + q) * (r_star_au / a_au) ** 8 / t_conv * YEAR_S
    ra = -k / 9 * (2 * f2 + e**2 * (7 / 8 * f1 - 10 * f2 + 441 / 8 * f3))
    re = -k / 36 * (5 / 4 * f1 - 2 * f2 + 147 / 4 * f3)
    return ra, re


def chromosphere_density_g_cm3(height_au, g_cgs):
    """Schröder & Connon Smith 2008 §4.2: today's low solar chromosphere, density × g/g☉ and heights
    × g☉/g. shortcut: an order-of-magnitude estimate they call the largest uncertainty; flagged
    where drag matters (DRAG_FLAG_SHARE)."""
    scale = np.asarray(g_cgs, float) / G_SUN_CGS
    h_scale = CHROMOSPHERE_HEIGHT_CM / scale
    rho0 = CHROMOSPHERE_N_CM3 * CHROMOSPHERE_PARTICLE_G * scale
    return rho0 * np.exp(1 - np.maximum(np.asarray(height_au) * AU_CM, 0.0) / h_scale)


def drag_rate_per_yr(a_au, e, m_planet_msun, m_star_msun, r_star_au):
    """ȧ/a (per year) from chromospheric drag: F_d = λ_d 4πρ (G M_p / c_s)², dΛ/dt = -F_d a with
    Λ = M_p (G M★ a)^½, so ȧ/a = -2 F_d a / Λ. shortcut: ρ is taken at the pericentre height for
    the whole orbit, an upper bound like λ_d = 3; e is left unchanged by drag."""
    a_cm = np.asarray(a_au, float) * AU_CM
    g = G_CGS * m_star_msun * MSUN_G / (r_star_au * AU_CM) ** 2
    rho = chromosphere_density_g_cm3(np.asarray(a_au) * (1 - np.asarray(e)) - r_star_au, g)
    mp = np.asarray(m_planet_msun, float) * MSUN_G
    force = DRAG_LAMBDA * 4 * np.pi * rho * (G_CGS * mp / SOUND_SPEED_CM_S) ** 2
    return -2 * force * a_cm / (mp * np.sqrt(G_CGS * m_star_msun * MSUN_G * a_cm)) * YEAR_S


def drag_decay_time_yr(a_au, m_planet_msun, m_star_msun, rho_g_cm3):
    """Schröder & Connon Smith's angular-momentum decay time Λ / |dΛ/dt| at a given density."""
    mp = m_planet_msun * MSUN_G
    a_cm = a_au * AU_CM
    force = DRAG_LAMBDA * 4 * np.pi * rho_g_cm3 * (G_CGS * mp / SOUND_SPEED_CM_S) ** 2
    return mp * np.sqrt(G_CGS * m_star_msun * MSUN_G * a_cm) / (force * a_cm) / YEAR_S


def _orbit_decay(a, e, mp, dt, m_s, m_env, r, l):
    """Tides and drag over dt years for one stretch of track (midpoint sub-steps, at most
    MAX_ORBIT_CHANGE in a and e each). Stops a planet once its pericentre reaches r. Returns a, e
    and the inward shift in ln a from tides and from drag."""
    a, e = a.copy(), e.copy()
    left = np.full(a.shape, float(dt))
    d_tide, d_drag = np.zeros(a.shape), np.zeros(a.shape)

    def rates(ai, ei, mi):
        ra, re = (tide_rates_per_yr(ai, ei, mi, m_s, m_env, r, l) if m_env > 0
                  else (np.zeros(ai.shape), np.zeros(ai.shape)))
        return ra, re, drag_rate_per_yr(ai, ei, mi, m_s, r)

    for _ in range(MAX_SUBSTEPS):
        go = np.flatnonzero((left > 0) & (a * (1 - e) > r))
        if go.size == 0:
            return a, e, d_tide, d_drag
        ra0, re0, rd0 = rates(a[go], e[go], mp[go])
        h = np.minimum(left[go], MAX_ORBIT_CHANGE
                       / np.maximum(np.maximum(np.abs(ra0 + rd0), np.abs(re0)), 1e-300))
        # Midpoint rule; near the star the midpoint rate can far exceed the starting one, so a
        # step whose midpoint rate would change a or e by over twice the limit is halved
        while True:
            ra, re, rd = rates(a[go] * (1 + 0.5 * h * (ra0 + rd0)), e[go] * (1 + 0.5 * h * re0),
                               mp[go])
            bad = np.maximum(np.abs(ra + rd), np.abs(re)) * h > 2 * MAX_ORBIT_CHANGE
            if not bad.any():
                break
            h = np.where(bad, 0.5 * h, h)
        a[go] *= 1 + h * (ra + rd)
        e[go] *= 1 + h * re
        d_tide[go] -= h * ra
        d_drag[go] -= h * rd
        left[go] -= h
    raise RuntimeError("orbit decay did not finish within MAX_SUBSTEPS")


def _strip(core, env, a, a_flux, l_xuv, m_star, age, dt):
    """Energy-limited escape over dt years, sub-stepped so no step removes more than 20% of an
    envelope; the flux is taken at a_flux (orbit-averaged). Returns the new envelopes and where
    Owen & Wu's model did not apply."""
    env, left = env.copy(), np.full(env.shape, float(dt))
    outside = np.zeros(env.shape, bool)
    period_d = _period_s(a, m_star + (core + env) / M_EARTH_PER_MSUN) / 86400
    for _ in range(200):     # each sub-step ends a planet's time or takes 20%: 0.8²⁰⁰ ≪ 1e-9
        go = (left > 0) & (env > ENVELOPE_GONE * core)
        if not go.any():
            break
        r, valid = escape.radius_rearth(core[go], env[go], period_d[go], m_star, age)
        outside[go] |= ~valid
        rate = escape.mass_loss_mearth_yr(r, core[go] + env[go], a_flux[go], l_xuv)
        h = np.minimum(left[go], 0.2 * env[go] / np.maximum(rate, 1e-300))
        env[go] = env[go] - rate * h
        left[go] -= h
    env[env <= ENVELOPE_GONE * core] = 0.0
    return env, outside


def _debounce(events: list[dict]) -> list[dict]:
    """Drop habitable-zone entries and exits that the next one undoes within HZ_MIN_STAY_YR: the
    zone's edge swings back and forth across an orbit while a giant's luminosity jumps."""
    hz = ("enters habitable zone", "leaves habitable zone")
    out = list(events)
    while True:
        idx = [i for i, e in enumerate(out) if e["kind"] in hz]
        pair = next(((j, k) for j, k in pairwise(idx)
                     if out[k]["age_yr"] - out[j]["age_yr"] < HZ_MIN_STAY_YR), None)
        if pair is None:
            return out
        out = [e for i, e in enumerate(out) if i not in pair]


def evolve_planets(hist: StarHistory, a_au, mass_mearth, f_env, ice_rich, t_start_yr,
                   a_form_au=None, e=None) -> dict:
    """Every planet of one star through the star's life. Inputs are per planet (arrays) as Phase 5
    leaves them when the gas disk is gone (t_start_yr); e defaults to circular orbits. Returns the
    exported ages and, per planet, the orbit (a, e) at those ages, its events, fate, closest
    approach and flags. t_start_yr may be one age or one per planet (each system's own disk
    lifetime)."""
    a = np.array(a_au, float)
    ecc = np.zeros(len(a)) if e is None else np.array(e, float)
    e0 = ecc.copy()
    m0 = np.array(mass_mearth, float)
    f0 = np.array(f_env, float)
    ice = np.array(ice_rich, bool)
    a_form = a.copy() if a_form_au is None else np.asarray(a_form_au, float)
    n = len(a)
    t_start_yr = np.broadcast_to(np.asarray(t_start_yr, float), (n,))
    core, env = m0 * (1 - f0), m0 * f0
    cls = classify(m0, f0, ice)
    events: list[list[dict]] = [[] for _ in range(n)]
    flags: list[set[str]] = [set() for _ in range(n)]
    alive, formed = np.ones(n, bool), np.zeros(n, bool)
    crossed = np.zeros(n, bool)
    in_hz = np.zeros(n, bool)
    dose = np.zeros(n)   # from the disk's end
    fate = np.full(n, "", dtype=object)
    min_ratio, min_phase = np.full(n, np.inf), np.full(n, "", dtype=object)
    earth = earth_fluence_lsun_yr()
    t, s = hist.age_yr, len(hist.age_yr)
    samples = np.unique(np.linspace(0, s - 1, OUTPUT_SAMPLES).round().astype(int))
    series = np.full((n, len(samples)), np.nan)
    e_series = np.full((n, len(samples)), np.nan)
    sample_at = {int(k): j for j, k in enumerate(samples)}
    shift_tide, shift_drag = np.zeros(n), np.zeros(n)
    straddle_yr = np.zeros(n)     # time in the zone by mean flux with q or Q outside it

    def record(k):
        if k in sample_at:
            series[alive, sample_at[k]] = a[alive]
            e_series[alive, sample_at[k]] = ecc[alive]

    record(0)

    def add(i, k, kind, detail):
        events[i].append({"age_yr": float(f"{t[k]:.5g}"), "kind": kind, "detail": detail})

    for k in range(s - 1):
        dt = t[k + 1] - t[k]
        new = alive & ~formed & (t[k + 1] >= t_start_yr)
        for i in np.flatnonzero(new):
            add(i, k + 1, "formed", f"{cls[i]}, {m0[i]:.3g} M⊕ at {a[i]:.3g} AU "
                f"(grew from {a_form[i]:.3g} AU)")
        formed |= new
        go = alive & formed
        if not go.any():
            record(k + 1)
            continue
        m_s0, m_s1 = hist.mass_msun[k], hist.mass_msun[k + 1]
        r1 = hist.radius_au[k + 1]
        mp = (core + env) / M_EARTH_PER_MSUN

        # 1. Mass loss widens the orbit
        a[go] *= m_s0 / m_s1
        p_s = _period_s(a, m_s1 + mp)
        if dt > 0 and m_s1 != m_s0:
            psi = abs(np.log(m_s0 / m_s1)) / (dt * YEAR_S) * p_s / (2 * np.pi)
            for i in np.flatnonzero(go & (psi > ADIABATIC_LIMIT)):
                flags[i].add("orbit_widening_not_adiabatic: mass loss fast next to the orbit")

        # 2. Tides and chromospheric drag once the star has left the main sequence
        if hist.phase[k] >= TIDES_FROM_PHASE and dt > 0:
            m_s = 0.5 * (m_s0 + m_s1)
            m_env = max(m_s - 0.5 * (hist.core_msun[k] + hist.core_msun[k + 1]), 0.0)
            r_mid = 0.5 * (hist.radius_au[k] + r1)
            l_mid = 0.5 * (hist.l_lsun[k] + hist.l_lsun[k + 1])
            idx = np.flatnonzero(go)
            a[idx], ecc[idx], d_t, d_d = _orbit_decay(a[idx], ecc[idx], mp[idx], dt, m_s, m_env,
                                                      r_mid, l_mid)
            shift_tide[idx] += d_t
            shift_drag[idx] += d_d

        # 3. Engulfment at pericentre
        ratio = a * (1 - ecc) / r1
        closer = go & (ratio < min_ratio)
        min_ratio[closer] = ratio[closer]
        min_phase[closer] = hist.phase_name(k + 1)
        for i in np.flatnonzero(go & (ratio <= 1)):
            alive[i] = False
            fate[i] = "engulfed"
            min_ratio[i] = 1.0
            add(i, k + 1, "engulfed", f"inside the star ({r1 / R_SUN_AU:.3g} R☉) during the "
                f"{hist.phase_name(k + 1)}")
        go &= alive

        # 4. XUV dose, shoreline label and envelope escape
        a_flux = flux_distance_au(a, ecc)
        dose[go] += (hist.fluence[k + 1] - hist.fluence[k]) / earth / a_flux[go] ** 2
        m_now = core + env
        v_esc = V_ESC_EARTH_KMS * np.sqrt(m_now / radius_rearth(m_now))
        cross = go & ~crossed & (dose >= shoreline.critical_dose(v_esc))
        for i in np.flatnonzero(cross):
            add(i, k + 1, "crosses shoreline", f"XUV dose {dose[i]:.3g} Earth doses against "
                f"{float(shoreline.critical_dose(v_esc[i])):.3g} for v_esc {v_esc[i]:.3g} km/s")
        crossed |= cross
        has_env = go & (env > 0)
        if has_env.any() and dt > 0:
            l_xuv = 0.5 * (hist.l_xuv_lsun[k] + hist.l_xuv_lsun[k + 1])
            new_env, outside = _strip(core[has_env], env[has_env], a[has_env],
                                      a_flux[has_env], l_xuv, m_s1,
                                      0.5 * (t[k] + t[k + 1]), dt)
            idx = np.flatnonzero(has_env)
            for i in idx[outside]:
                flags[i].add("radius_from_chen_kipping: envelope too massive for Owen & Wu's "
                             "thin-envelope model")
            for i in idx[(new_env == 0)]:
                add(i, k + 1, "envelope stripped", "energy-limited escape removed the last of "
                    "the hydrogen-helium envelope")
            env[has_env] = new_env

        # 5. Classes again
        m_now = core + env
        new_cls = classify(m_now, env / m_now, ice)
        for i in np.flatnonzero(go & (new_cls != cls)):
            add(i, k + 1, "class changed", f"{cls[i]} → {new_cls[i]} (envelope fraction "
                f"{env[i] / m_now[i]:.3g})")
        cls = np.where(go, new_cls, cls)

        # 6. Habitable zone, where it is defined
        lo, hi = hist.hz_inner_au[k + 1], hist.hz_outer_au[k + 1]
        if np.isfinite(lo):
            inside = go & (a_flux >= lo) & (a_flux <= hi)
            straddle_yr[inside & ((a * (1 - ecc) < lo) | (a * (1 + ecc) > hi))] += dt
            for i in np.flatnonzero(inside & ~in_hz):
                add(i, k + 1, "enters habitable zone", f"{lo:.3g}-{hi:.3g} AU")
            for i in np.flatnonzero(go & ~inside & in_hz):
                add(i, k + 1, "leaves habitable zone", f"{lo:.3g}-{hi:.3g} AU")
            in_hz = np.where(go, inside, in_hz)

        record(k + 1)

    # The star's end
    end = s - 1
    ending = hist.track.ending
    m_end = hist.mass_msun[end]
    survivors = np.flatnonzero(alive & formed)
    if ending == "white-dwarf cooling sequence":
        for i in survivors:
            fate[i] = "orbits white dwarf"
            add(i, end, "orbits remnant", f"white dwarf of {m_end:.3g} M☉ at {a[i]:.3g} AU, "
                f"{m_end and hist.mass_msun[0] / m_end:.3g}× its main-sequence orbit")
    elif ending.startswith(CARBON_END) and hist.track.star_type == "high-mass":
        from ..remnants import remnant
        rem = remnant(hist.track, hist.track.mass_msun)
        for i in survivors:
            if rem.type not in ("neutron star", "black hole", "none"):
                fate[i] = "unresolved"
                add(i, end, "track ends", f"no remnant predicted ({rem.type})")
            elif supernova_unbinds(m_end, rem.mass_msun or 0.0,
                                   (core[i] + env[i]) / M_EARTH_PER_MSUN):
                fate[i] = "unbound"
                add(i, end, "unbound", f"the star's death leaves {rem.mass_msun or 0:.3g} of "
                    f"{m_end:.3g} M☉ ({rem.type}); more than half the mass lost at once")
            else:
                fate[i] = f"orbits {rem.type}"
                flags[i].add("natal_kick_not_modelled: survival is an upper limit")
                add(i, end, "orbits remnant", f"{rem.type} of {rem.mass_msun:.3g} M☉")
    else:
        for i in survivors:
            fate[i] = "unresolved"
            add(i, end, "track ends", f"the MIST track stops at {ending}, age {t[end]:.3g} yr")

    m_final = core + env
    f_final = env / m_final
    drag_share = shift_drag / np.maximum(shift_tide + shift_drag, 1e-300)
    for i in np.flatnonzero(formed & (drag_share > DRAG_FLAG_SHARE)):
        flags[i].add(f"chromospheric_drag_matters: {100 * drag_share[i]:.3g}% of the inward drift "
                     "is drag, whose density is an order-of-magnitude estimate")
    for i in np.flatnonzero(straddle_yr >= HZ_MIN_STAY_YR):
        flags[i].add(f"habitable_zone_partly_outside_orbit: for {straddle_yr[i]:.3g} yr the "
                     "mean-flux distance is in the zone but the pericentre or apocentre is not")
    for i in np.flatnonzero(formed):
        if f0[i] >= F_ENV_ENVELOPE and crossed[i] != (f_final[i] < F_ENV_ENVELOPE):
            flags[i].add("shoreline_and_escape_disagree: the shoreline label says the air is "
                         f"{'lost' if crossed[i] else 'kept'}, energy-limited escape leaves "
                         f"envelope fraction {f_final[i]:.3g}")
    return {
        "samples": samples, "sample_age_yr": t[samples], "a_au": series, "e": e_series,
        "initial_e": e0, "final_e": ecc, "fate": fate.astype(str),
        "closest_approach_rstar": min_ratio, "deciding_phase": min_phase.astype(str),
        "events": [_debounce(e) for e in events], "flags": [sorted(f) for f in flags],
        "final_a_au": a,
        "final_mass_mearth": m_final, "final_f_env": f_final, "final_class": cls,
        "xuv_dose_earth": dose, "shoreline_crossed": crossed,
        "air_retained": shoreline.air_retained(dose, V_ESC_EARTH_KMS * np.sqrt(
            m_final / radius_rearth(m_final))),
    }


# ---- Reference cases (build plan, Phase 6 Validation) ----------------------------------------

# (name, mass M⊕, orbit today AU, envelope fraction, ice-rich core, eccentricity); NASA planetary
# fact sheet masses, orbits and eccentricities; giant envelope fractions are rough round numbers
# that only fix their class.
SOLAR_SYSTEM = (("Mercury", 0.0553, 0.387, 0.0, False, 0.2056),
                ("Venus", 0.815, 0.723, 0.0, False, 0.0068),
                ("Earth", 1.0, 1.0, 0.0, False, 0.0167), ("Mars", 0.107, 1.524, 0.0, False, 0.0935),
                ("Jupiter", 317.8, 5.203, 0.9, True, 0.0489),
                ("Saturn", 95.16, 9.537, 0.8, True, 0.0565),
                ("Uranus", 14.54, 19.19, 0.1, True, 0.0457),
                ("Neptune", 17.15, 30.07, 0.1, True, 0.0113))
SOLAR_DISK_END_YR = 3e6     # a typical disk lifetime (Phase 5 draws 1-10 Myr)


@lru_cache(maxsize=1)
def solar_system() -> tuple[StarHistory, dict]:
    """The Solar System on MIST's own 1 M☉, [Fe/H] 0 track."""
    hist = star_history(build_track(1.0, 0.0))
    _, m, a, f, ice, e = zip(*SOLAR_SYSTEM)
    return hist, evolve_planets(hist, a, m, f, ice, SOLAR_DISK_END_YR, e=e)


def earth_habitable_zone_timing() -> dict:
    """When each inner-edge limit passes 1 AU on the MIST Sun, counted from 4.57 Gyr and from the
    age at which MIST's Sun is 1 L☉ (MIST's released solar track is brighter than the Sun at
    4.57 Gyr; evolution tests)."""
    hist = star_history(build_track(1.0, 0.0))
    ms = slice(np.searchsorted(hist.age_yr, 1e9), np.searchsorted(hist.age_yr, 1.05e10))
    age, lum, teff = hist.age_yr[ms], hist.l_lsun[ms], hist.teff_k[ms]
    one_lsun = float(np.interp(1.0, lum, age))      # luminosity rises monotonically here
    out = {"age_at_1_lsun_yr": one_lsun}
    for limit in ("moist greenhouse", "runaway greenhouse"):
        edge = habitable_edge_au(limit, lum, teff)
        passes = float(np.interp(1.0, edge, age))
        out[limit] = {"passes_1_au_yr": passes, "after_1_lsun_gyr": (passes - one_lsun) / 1e9,
                      "after_4_57_gyr": (passes - 4.57e9) / 1e9,
                      "edge_at_4_57_au": float(np.interp(4.57e9, age, edge))}
    return out
