"""Population synthesis: thousands of disks, each with a row of planetary seeds, integrated through
core growth, gas capture and migration until the gas disk is gone (Ida & Lin 2004a §3.2, 2008a §3.3).

The recipe, per seed (the gas phase of Ida, Lin & Nagasawa 2013, "Paper VII", ida_lin_2013.py;
equation numbers are Paper VII's unless stated):

- solids: dM_c/dt = M_c / τ_c,acc (eq. 19), up to the isolation mass (Ida & Lin 2004a eq. 20) and
  the solids of the seed's own annulus;
- gas: once M_c > M_c,hydro(Ṁ_c) (Ida & Lin 2004a eq. 33, from Ikoma et al. 2000),
  dM/dt = f_gap min(M / τ_KH, Ṁ_disk) (eqs. 23-31), ending at the thermal gap mass M_g,th (eq. 28);
- migration: type I as C1 times Tanaka et al. 2002 (eq. 22); type II from the viscous gap mass
  M_g,vis (eq. 27), disk- or planet-dominated (eqs. 32, 34), inward inside r_m (derived from eqs.
  32-33, ida_lin_2013.viscous_couple_radius_au); stopped at the inner edge. An embryo
  that closes on its inner neighbour is trapped in resonance 5 Hill radii outside it, so convoys
  park in a chain outward from the inner edge (Ida & Lin 2010 §2.4-2.5), and a seed that has
  migrated to half its starting radius leaves a next-generation seed there (2010 §2.5);
- disks: log10 f_g,0 Gaussian with σ = 1 about (M★/M☉)^k, kept within 0.1-10 times it (§5.1),
  with k = 1 (disk mass roughly linear in M★, Andrews et al. 2013; the default) or k = 2 (Ida &
  Lin 2005); f_d,0 = f_g,0 10^[Fe/H]; τ_disk log-uniform in 1-10 Myr; 15 seeds log-uniform in
  0.05-50 AU at M_c = 10²⁰ g (Ida & Lin 2008a §3.3).

Each step integrates the rates in closed form with the disk held at its mid-step state: τ_c,acc ∝
M^1/3 makes M^1/3 grow linearly, τ_KH ∝ M⁻³ makes M⁻³ fall linearly, and each migration rate
is a power law ȧ ∝ a^n, so a^(1-n) moves linearly. The gap taper f_gap is read at the start of
each step, so the gas-giant share drifts slightly with step size (tests bound it).

Each seed stands for the oligarchs of its own annulus (between the midpoints to its neighbouring
seeds): its solids are capped by the annulus's, so neighbouring feeding zones never share material.

Multiplicity, version 2 (build plan): once the gas is gone (f_g < 10⁻³ f_g,0, the condition Ida &
Lin 2010 §3.1 use), the oligarchs of each annulus merge by giant impacts (Ida & Lin 2004a eq. 24)
and neighbouring planets cross orbits and merge (Ida & Lin 2010; impacts.py), to T_FINAL_YR.
"""

from itertools import pairwise

import numpy as np

from . import M_EARTH_PER_MSUN
from . import ida_lin_2013 as vii
from .classify import classify
from .disk import f_dust, gas_factor, sigma_dust, snow_line_au
from .growth import (
    ALPHA_DEFAULT,
    critical_core_mass,
    isolation_mass,
    kelvin_helmholtz_time_yr,
)
from .impacts import (
    bulk_density,
    crossing_time_yr,
    embryo_accretion_time_yr,
    embryo_isolation_mass,
    escape_eccentricity,
    merged_orbit,
)
from .migration import C1_DEFAULT, INNER_EDGE_AU
from .radius import radius_rearth

SEEDS = 15                      # per disk, log-uniform in SEED_RANGE_AU (Ida & Lin 2008a §3.3)
SEED_RANGE_AU = (0.05, 50.0)
SEED_MASS = 1e20 / 5.9722e27    # 10²⁰ g in M⊕ (Ida & Lin 2004a §2.5, 2008a §3.3)
F_G_SIGMA_DEX = 1.0             # spread of log10 f_g,0 (Ida & Lin 2004a §4.2)
F_G_RANGE = (0.1, 10.0)         # f_g,0 / (M★/M☉)^k is kept within this (Ida, Lin & Nagasawa 2013 §5.1)
TAU_DISK_RANGE_YR = (1e6, 1e7)  # log-uniform (2004a §4.2; 2008a §3.3)
DISK_MASS_SCALINGS = {"linear": 1.0, "ida-lin": 2.0}   # f_g,0 centred on M★^k
GAS_GONE = 1e-3                 # f_g / f_g,0 below which orbits may cross (Ida & Lin 2010 §3.1)
T_FINAL_YR = 1e9                # giant impacts run until crossing times exceed a Gyr (2010 §2.6)
B_TRAP_HILL = 5.0               # resonant spacing of convoy members, Hill radii (2010 §2.4)
NEXT_GEN_MASS_SHARE = 1e-2      # a next-generation seed starts at this share of its predecessor
COLLIDE_LAG_LOG_TK = (5.5, 6.5) # closely packed pairs collide after 10^5.5-6.5 T_K (2010 step 8)
E_MAX = 0.9
MAX_ENCOUNTERS = 60             # per system; each is one close encounter, with or without a merger
T_START_YR = 1e5                # the first step covers 0-0.1 Myr in closed form, then log steps
STEPS_PER_DEX = 100
M_MIN_PLANET = 0.1              # M⊕: smaller bodies are left out of the planet counts (about Mars)
AU_CM = 1.495978707e13
G_PER_MEARTH = 5.9722e27

DEFAULTS = {"c1": C1_DEFAULT, "alpha": ALPHA_DEFAULT, "disk_mass_scaling": "linear",
            "f_g_sigma_dex": F_G_SIGMA_DEX, "tau_disk_range_yr": TAU_DISK_RANGE_YR,
            "steps_per_dex": STEPS_PER_DEX}


def draw_disks(n: int, m_star_msun: float, feh: float, rng: np.random.Generator,
               disk_mass_scaling: str = "linear", f_g_sigma_dex: float = F_G_SIGMA_DEX,
               tau_disk_range_yr=TAU_DISK_RANGE_YR) -> dict:
    """n disks: f_g,0, f_d,0, τ_disk and sorted seed radii (n × SEEDS), as Ida & Lin 2008a §3.3."""
    centre = DISK_MASS_SCALINGS[disk_mass_scaling] * np.log10(m_star_msun)
    log_fg = np.empty(n)
    todo = np.arange(n)
    while todo.size:      # draws outside F_G_RANGE (times the centre) are redrawn
        log_fg[todo] = rng.normal(centre, f_g_sigma_dex, todo.size)
        off = np.abs(log_fg[todo] - centre - np.mean(np.log10(F_G_RANGE))) \
            > np.diff(np.log10(F_G_RANGE))[0] / 2
        todo = todo[off]
    f_g0 = 10.0**log_fg
    lo, hi = np.log10(tau_disk_range_yr)
    tau = 10.0 ** rng.uniform(lo, hi, n)
    a = np.sort(10.0 ** rng.uniform(*np.log10(SEED_RANGE_AU), (n, SEEDS)), axis=1)
    return {"f_g0": f_g0, "f_d0": f_dust(f_g0, feh), "tau_disk_yr": tau, "a0_au": a}


def annulus_bounds(a_au):
    """Each seed's annulus: from the geometric midpoint to its inner neighbour to that to its outer
    one, closed by the seed range."""
    edges = np.sqrt(a_au[:, 1:] * a_au[:, :-1])
    lo = np.concatenate([np.full((len(a_au), 1), SEED_RANGE_AU[0]), edges], axis=1)
    hi = np.concatenate([edges, np.full((len(a_au), 1), SEED_RANGE_AU[1])], axis=1)
    return lo, hi


def annulus_solids(a_au, f_d, a_ice):
    """Solids (M⊕) in each seed's annulus: ∫ 2π a Σ_d da with Σ_d of eq. 11 (∝ a^-3/2, stepped at
    the snow line)."""
    lo, hi = annulus_bounds(a_au)

    def inside(r):   # ∫_0^r 2π a Σ_d da in M⊕: 4π Σ_d0 f_d (AU in cm)² r^1/2 / g per M⊕
        unit = 4 * np.pi * 10.0 * f_d[:, None] * AU_CM**2 / G_PER_MEARTH
        r_ice = np.minimum(r, a_ice)
        return unit * (np.sqrt(r_ice) + 4.2 * (np.sqrt(np.maximum(r, a_ice)) - np.sqrt(a_ice)))
    return inside(hi) - inside(lo)


def time_grid(t_end_yr: float, steps_per_dex: int = STEPS_PER_DEX) -> np.ndarray:
    n = max(2, int(np.ceil(np.log10(t_end_yr / T_START_YR) * steps_per_dex)) + 1)
    return np.concatenate([[0.0], np.geomspace(T_START_YR, t_end_yr, n)])


def evolve(disks: dict, m_star_msun: float, c1: float = C1_DEFAULT, alpha: float = ALPHA_DEFAULT,
           steps_per_dex: int = STEPS_PER_DEX) -> dict:
    """Integrate every seed of every disk. Returns arrays (systems × 2 seeds per annulus, the second
    a next-generation seed or empty): core and envelope mass (M⊕), final and formation radius (AU),
    whether the core is ice-rich, the solids each may still draw on, and the snow line.

    Next-generation seeds (Ida & Lin 2010 §2.5): once a seed has migrated to half its starting
    radius, a new seed of NEXT_GEN_MASS_SHARE of its mass starts at that radius and grows from
    the planetesimals it left there; the migrant keeps what it has. shortcut: one new generation
    per annulus, where the paper allows more."""
    n_seeds = disks["a0_au"].shape[1]
    a0 = np.tile(disks["a0_au"], 2)
    a = a0.copy()
    tau = disks["tau_disk_yr"][:, None]
    f_g0, f_d = disks["f_g0"][:, None], disks["f_d0"][:, None]
    a_ice = float(snow_line_au(m_star_msun))
    solids_cap = np.tile(annulus_solids(disks["a0_au"], disks["f_d0"], a_ice), 2)
    core = np.concatenate([np.full(disks["a0_au"].shape, SEED_MASS),
                           np.zeros(disks["a0_au"].shape)], axis=1)   # empty until spawned
    env = np.zeros(a.shape)
    a_form = a.copy()
    spawned = np.zeros(disks["a0_au"].shape, bool)
    gap = np.zeros(a.shape, bool)           # opened a gap: type II, no more gas
    m_star_mearth = m_star_msun * M_EARTH_PER_MSUN
    t_end = tau * np.log(1 / GAS_GONE)
    times = time_grid(float(t_end.max()), steps_per_dex)
    for t0, t1 in pairwise(times):
        live = t0 < t_end                     # this disk still has gas
        if not live.any():
            break
        dt = np.where(live, t1 - t0, 0.0)
        tm = np.minimum(0.5 * (t0 + t1), t_end)
        f_g = gas_factor(f_g0, tm, tau)
        m = core + env
        eta = np.where(a > a_ice, 4.2, 1.0)
        # Solids, Paper VII eq. 19: τ = K M^1/3, so M^1/3 rises by dt / 3K; capped at isolation (eq. 20)
        # and at the annulus's own solids
        k = vii.core_accretion_time_yr(1.0, a, f_d, f_g, eta, m_star_msun)
        iso = np.minimum(isolation_mass(sigma_dust(a, f_d, a_ice), a, m_star_msun), solids_cap)
        active = core > 0
        growing = active & (core < iso)
        grown = (np.cbrt(core) + dt / (3 * k)) ** 3 - core      # eq. 19: the core's own mass
        new_core = np.where(growing, np.minimum(core + grown, iso), core)
        mdot_core = np.where(growing, (new_core - core) / np.maximum(dt, 1e-30), 0.0)
        a_form = np.where(new_core > core * (1 + 1e-9), a, a_form)
        core = new_core
        # Gas (Ida, Lin & Nagasawa 2013 eqs. 23-31): dM/dt = f_gap min(M/τ_KH, Ṁ_disk) once the
        # core passes M_c,hydro. τ_KH = 10⁹ M⁻³, so M⁻³ falls by 3 dt / 10⁹; Ṁ_disk adds at most
        # Ṁ_disk dt; f_gap, read at the start of the step, tapers both to 0 at M_g,th
        m = core + env
        ceiling = vii.thermal_gap_mass(a, m_star_msun)
        accreting = active & (core > critical_core_mass(mdot_core)) & (m < ceiling)
        left = np.maximum(m, SEED_MASS) ** -3 - 3 * dt / kelvin_helmholtz_time_yr(1.0)
        m_kh = np.where(left > 0, np.abs(left) ** (-1 / 3), np.inf)
        f_gap = vii.gap_factor(m, a, m_star_msun, alpha)
        gained = f_gap * np.minimum(m_kh - m, vii.disk_accretion_rate(f_g, alpha) * dt)
        env = np.where(accreting, env + np.clip(np.minimum(gained, ceiling - m), 0.0, None), env)
        m = core + env
        gap |= m >= vii.viscous_gap_mass(a, m_star_msun, alpha)     # type II from M_g,vis
        # Migration (Ida, Lin & Nagasawa 2013 eqs. 22, 32, 34): each rate is a power law ȧ ∝ a^n,
        # so a^(1-n) moves linearly in time; n is read off the rate itself
        r_m = vii.viscous_couple_radius_au(tm, tau, m_star_msun, alpha)
        here, nudged = (np.where(gap, vii.type2_rate(r, m, f_g, r_m, m_star_msun, alpha),
                                 vii.type1_rate(r, np.maximum(m, SEED_MASS), f_g, m_star_msun, c1))
                        for r in (a, a * 1.01))
        with np.errstate(divide="ignore", invalid="ignore"):     # empty slots: no rate
            n_pow = np.clip(np.log(np.abs(nudged / here)) / np.log(1.01), -1.0, 0.9)
        n_pow = np.where(active, n_pow, 0.0)
        e = 1 - n_pow
        moved = a**e + e * a ** -n_pow * np.where(active, here, 0.0) * dt
        edge = moved <= INNER_EDGE_AU**e
        new_a = np.where(edge, INNER_EDGE_AU, np.abs(moved) ** (1 / e))
        a = np.where(active & (a > INNER_EDGE_AU), new_a, a)
        # Next generation (Ida & Lin 2010 §2.5)
        spawn = live & ~spawned & (core[:, :n_seeds] > 0) & (a[:, :n_seeds] < 0.5 * a0[:, :n_seeds])
        if spawn.any():
            child = np.flatnonzero(spawn.ravel())
            rows, cols = np.unravel_index(child, spawn.shape)
            left_over = np.maximum(solids_cap[rows, cols] - core[rows, cols], 0.0)
            core[rows, cols + n_seeds] = np.minimum(NEXT_GEN_MASS_SHARE * core[rows, cols],
                                                    left_over)
            solids_cap[rows, cols + n_seeds] = left_over
            solids_cap[rows, cols] = core[rows, cols]      # the migrant keeps what it has
            spawned |= spawn
        # Resonant convoys (Ida & Lin 2010 §2.4): an embryo closing on its inner neighbour is held
        # B_TRAP_HILL mutual Hill radii outside it, so seeds never overtake and pile outward from
        # the inner edge. shortcut: the convoy moves at its leader's rate instead of sharing the
        # members' torques; replace if convoy speeds matter.
        m = core + env
        order = np.argsort(np.where(m > 0, a, np.inf), axis=1)
        a_s, m_s = np.take_along_axis(a, order, axis=1), np.take_along_axis(m, order, axis=1)
        for k in range(1, a.shape[1]):
            both = (m_s[:, k] > 0) & (m_s[:, k - 1] > 0)
            r_h = ((m_s[:, k - 1] + m_s[:, k]) / (3 * m_star_mearth)) ** (1 / 3) * a_s[:, k - 1]
            a_s[:, k] = np.where(both, np.maximum(a_s[:, k], a_s[:, k - 1] + B_TRAP_HILL * r_h),
                                 a_s[:, k])
        np.put_along_axis(a, order, a_s, axis=1)
    return {"core_mearth": core, "env_mearth": env, "a_au": a, "a_form_au": a_form,
            "ice_rich": a_form > a_ice, "a_ice_au": a_ice, "solids_cap": solids_cap,
            "t_gas_gone_yr": t_end[:, 0]}


def after_gas(state: dict, disks: dict, m_star_msun: float, rng: np.random.Generator,
              t_final_yr: float = T_FINAL_YR) -> dict:
    """Giant impacts once the gas is gone (multiplicity version 2), to t_final_yr.

    1. Inside each annulus the oligarchs merge: dM_e/dt = M_e / τ_e,acc (Ida & Lin 2004a eq. 24),
       up to the embryo isolation mass (eq. 25's definition) and the annulus's solids.
    2. Between seeds, the neighbouring pair with the shortest crossing time (Zhou et al. 2007) has
       a close encounter, one per system per round, until the next comes after t_final_yr (Ida &
       Lin 2010, Appendix steps 2-3 and 5-8). Eccentricities start Rayleigh-distributed about the
       Hill eccentricity (step 1). The encounter excites the pair to the escape eccentricity,
       shared by mass (eqs. 17-18), and pushes them apart, conserving their orbital energy; then
       neighbours whose radial excursions overlap collide and merge (eqs. 19-20).
       Embryos still embedded in more planetesimals than their own mass do not cross (dynamical
       friction, Ida & Lin 2010 §3.1).

    shortcut: only the encountering pair is scattered; the rest of its group (Appendix step 4)
    keeps its orbits until its own encounter. Add it if eccentricities or spacings matter.
    shortcut: a merged body keeps the formation radius, so the core composition, of the heavier.
    shortcut: a merger adds the two envelopes, though a giant impact strips gas (Ida & Lin 2010
    leave envelopes out); replace with an impact-stripping prescription if envelopes of merged
    planets matter."""
    core, env = state["core_mearth"].copy(), state["env_mearth"].copy()
    a, a_form = state["a_au"].copy(), state["a_form_au"].copy()
    a_ice, n = state["a_ice_au"], len(a)
    m_star_mearth = m_star_msun * M_EARTH_PER_MSUN
    t = state["t_gas_gone_yr"].copy()
    f_d = disks["f_d0"][:, None]
    eta = np.where(a > a_ice, 4.2, 1.0)
    rho = bulk_density(a, a_ice)
    # 1. Within each annulus, closed form as in the gas phase: τ_e,acc ∝ M^1/3
    cap = np.minimum(embryo_isolation_mass(sigma_dust(a, f_d, a_ice), a, rho, m_star_msun),
                     state["solids_cap"])
    k = embryo_accretion_time_yr(1.0, a, f_d, eta, rho, m_star_msun)
    grown = (np.cbrt(core) + (t_final_yr - t)[:, None] / (3 * k)) ** 3
    core = np.where(core < cap, np.minimum(grown, cap), core)
    # Planetesimals left near each embryo: its annulus's, if it is still there
    lo, hi = (np.tile(x, a.shape[1] // x.shape[1]) for x in annulus_bounds(disks["a0_au"]))
    home = (a >= lo) & (a <= hi)
    residual = np.where(home, np.maximum(state["solids_cap"] - core, 0.0), 0.0)
    # 2. Orbit crossing between seeds
    m = core + env
    e = rng.rayleigh(np.sqrt(2 / np.pi), a.shape) * (m / (3 * m_star_mearth)) ** (1 / 3)
    rows = np.arange(n)
    for _ in range(MAX_ENCOUNTERS):
        order = np.argsort(a, axis=1)
        core, env, a, a_form, e, residual = (np.take_along_axis(x, order, axis=1)
                                             for x in (core, env, a, a_form, e, residual))
        m = core + env
        free = (m > 0) & (residual <= core)
        with np.errstate(divide="ignore", invalid="ignore"):
            tau = crossing_time_yr(m[:, :-1], m[:, 1:], a[:, :-1], a[:, 1:], e[:, :-1], e[:, 1:],
                                   m_star_msun)
        tau = np.where(free[:, :-1] & free[:, 1:] & np.isfinite(tau), tau, np.inf)
        j = np.argmin(tau, axis=1)
        best = tau[rows, j]
        t_k = np.sqrt(a[rows, j] * a[rows, np.minimum(j + 1, a.shape[1] - 1)]) ** 1.5 \
            / np.sqrt(m_star_msun)
        lag = np.where(best < 10**COLLIDE_LAG_LOG_TK[0] * t_k,
                       10 ** rng.uniform(*COLLIDE_LAG_LOG_TK, n) * t_k, best)
        go = np.isfinite(best) & (t + lag < t_final_yr)
        if not go.any():
            break
        t = np.where(go, t + lag, t)
        r, i = rows[go], j[go]
        mi, mj = m[r, i], m[r, i + 1]
        # Step 3: close encounters excite the pair to the escape eccentricity, shared by mass
        # (eqs. 17-18), and push them apart by e a each; step 5 rescales the two orbits so the
        # pair's orbital energy is conserved
        # shortcut: e_esc passes 1 for giant planets, which Ida & Lin 2010 leave out (they would be
        # ejected); excited eccentricities are capped at E_MAX and nothing is ejected
        e_esc = escape_eccentricity(mi + mj, a[r, i], bulk_density(a[r, i], a_ice), m_star_msun)
        e[r, i] = np.minimum(mj / (mi + mj) * e_esc * rng.rayleigh(np.sqrt(2 / np.pi), r.size),
                             E_MAX)
        e[r, i + 1] = np.minimum(mi / (mi + mj) * e_esc
                                 * rng.rayleigh(np.sqrt(2 / np.pi), r.size), E_MAX)
        a_i, a_j = a[r, i] * (1 - e[r, i]), a[r, i + 1] * (1 + e[r, i + 1])
        scale = (mi / a_i + mj / a_j) / (mi / a[r, i] + mj / a[r, i + 1])
        a[r, i], a[r, i + 1] = a_i * scale, a_j * scale
        # Step 6: a collision between neighbours whose radial excursions now overlap, the inner
        # pair first (collision probability ∝ a⁻³). shortcut: the inner overlapping pair always
        # collides, instead of a weighted random choice.
        hit = np.full(r.size, -1)
        for k in (i + 1, i, i - 1):                  # the last one written wins: innermost first
            ok = (k >= 0) & (k + 1 < a.shape[1])
            kk, k1 = np.clip(k, 0, a.shape[1] - 1), np.clip(k + 1, 0, a.shape[1] - 1)
            overlap = (m[r, kk] > 0) & (m[r, k1] > 0) & \
                (a[r, kk] * (1 + e[r, kk]) >= a[r, k1] * (1 - e[r, k1]))
            hit = np.where(ok & overlap, k, hit)
        r, k = r[hit >= 0], hit[hit >= 0]
        mk, ml = m[r, k], m[r, k + 1]
        theta = rng.uniform(np.pi / 2, 3 * np.pi / 2, r.size)   # periastra roughly opposed
        a_new, e_new = merged_orbit(mk, ml, a[r, k], a[r, k + 1], e[r, k], e[r, k + 1], theta)
        a_form[r, k] = np.where(ml > mk, a_form[r, k + 1], a_form[r, k])
        core[r, k] += core[r, k + 1]
        env[r, k] += env[r, k + 1]
        a[r, k], e[r, k] = a_new, e_new
        core[r, k + 1] = env[r, k + 1] = residual[r, k + 1] = 0.0
        a[r, k + 1] = np.inf                    # gone: sorts to the end
    a = np.where(np.isfinite(a), a, 0.0)
    return state | {"core_mearth": core, "env_mearth": env, "a_au": a, "a_form_au": a_form,
                    "ice_rich": a_form > a_ice, "e": e}


def planets(state: dict) -> dict:
    """The surviving planets (M_p ≥ M_MIN_PLANET) as flat arrays with their system index, class
    (classify.py) and display radius (radius.py)."""
    m = state["core_mearth"] + state["env_mearth"]
    keep = m >= M_MIN_PLANET
    system = np.nonzero(keep)[0]
    mass = m[keep]
    f_env = state["env_mearth"][keep] / mass
    ice = state["ice_rich"][keep]
    return {"system": system, "mass_mearth": mass, "f_env": f_env, "ice_rich": ice,
            "a_au": state["a_au"][keep], "a_form_au": state["a_form_au"][keep],
            "radius_rearth": radius_rearth(mass), "class": classify(mass, f_env, ice)}


def run_cell(m_star_msun: float, feh: float, n_systems: int, seed: int, **params) -> dict:
    """One cell of the grid: n_systems disks around one star, reproducible from `seed`."""
    p = DEFAULTS | params
    rng = np.random.default_rng(seed)
    disks = draw_disks(n_systems, m_star_msun, feh, rng, p["disk_mass_scaling"],
                       p["f_g_sigma_dex"], p["tau_disk_range_yr"])
    state = evolve(disks, m_star_msun, p["c1"], p["alpha"], p["steps_per_dex"])
    state = after_gas(state, disks, m_star_msun, rng)
    return {"disks": disks, "planets": planets(state), "n_systems": n_systems,
            "a_ice_au": state["a_ice_au"],
            "m_star_msun": m_star_msun, "feh": feh, "seed": seed, "params": p}

