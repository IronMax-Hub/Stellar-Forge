"""Population synthesis: thousands of disks, each with a row of planetary seeds, integrated through
core growth, gas capture and migration until the gas disk is gone (Ida & Lin 2004a §3.2, 2008a §3.3).

The recipe, per seed (Ida & Lin 2004a, §3.2 bullets; equation numbers are 2004a's unless stated):

- solids: dM_p/dt = M_p / τ_c,acc (eqs. 18, 32), until the core reaches its isolation mass
  (eq. 20), after which M_c,crit = 0;
- gas: once M_c > M_c,crit(Ṁ_c) (eq. 33), dM_p/dt = M_p / τ_KH (eq. 34), truncated by gap
  opening (M_g,th, eq. 38; 2004a's model b) or by the gas left in the disk (M_g,noiso, eq. 47);
- migration: type I below M_g,th (C1 times Tanaka et al. 2002, Ida & Lin 2008a eq. 12), type II
  from M_g,th (eqs. 65, 68, 70), stopped at the inner edge;
- disks: log10 f_g,0 Gaussian with σ = 1, cut at f_g,0 = 30, centred on (M★/M☉)^k with k = 1
  (disk mass roughly linear in M★, Andrews et al. 2013; the default) or k = 2 (Ida & Lin 2005);
  f_d,0 = f_g,0 10^[Fe/H]; τ_disk log-uniform in 1-10 Myr; 15 seeds log-uniform in 0.05-50 AU at
  M_c = 10²⁰ g (all Ida & Lin 2008a §3.3).

Each step integrates the rates in closed form with the disk held at its mid-step state: τ_c,acc ∝
M^1/3 makes M^1/3 grow linearly, τ_KH ∝ M⁻³ makes M⁻³ fall linearly, and each migration rate
is a power law ȧ ∝ a^n, so a^(1-n) moves linearly. So the result barely depends on the step (tests check it).

Multiplicity, version 1 (build plan): seeds are integrated independently, as in Ida & Lin 2008a,
but a core's solids are also capped by those in its own annulus (between the midpoints to its
neighbouring seeds), so neighbouring feeding zones never share material.
"""

from itertools import pairwise

import numpy as np

from .classify import classify
from .disk import f_dust, gas_factor, sigma_dust, snow_line_au
from .growth import (
    ALPHA_DEFAULT,
    core_accretion_time_yr,
    critical_core_mass,
    disk_gas_mass_limit,
    gap_opening_mass,
    isolation_mass,
    kelvin_helmholtz_time_yr,
)
from .migration import C1_DEFAULT, INNER_EDGE_AU, type1_rate, type2_rate

SEEDS = 15                      # per disk, log-uniform in SEED_RANGE_AU (Ida & Lin 2008a §3.3)
SEED_RANGE_AU = (0.05, 50.0)
SEED_MASS = 1e20 / 5.9722e27    # 10²⁰ g in M⊕ (Ida & Lin 2004a §2.5, 2008a §3.3)
F_G_SIGMA_DEX = 1.0             # spread of log10 f_g,0 (Ida & Lin 2004a §4.2)
F_G_MAX = 30.0                  # heavier disks are gravitationally unstable (2004a, eq. 56)
TAU_DISK_RANGE_YR = (1e6, 1e7)  # log-uniform (2004a §4.2; 2008a §3.3)
DISK_MASS_SCALINGS = {"linear": 1.0, "ida-lin": 2.0}   # f_g,0 centred on M★^k
# shortcut: the run stops when f_g has fallen to 10⁻³ of its start (t ≈ 6.9 τ_disk) and planets
# keep only what they had; post-gas giant impacts (Ida & Lin 2010) are multiplicity version 2.
GAS_GONE = 1e-3
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
    while todo.size:      # the cut at f_g,0 = 30 removes the tail: redraw it
        log_fg[todo] = rng.normal(centre, f_g_sigma_dex, todo.size)
        todo = todo[log_fg[todo] > np.log10(F_G_MAX)]
    f_g0 = 10.0**log_fg
    lo, hi = np.log10(tau_disk_range_yr)
    tau = 10.0 ** rng.uniform(lo, hi, n)
    a = np.sort(10.0 ** rng.uniform(*np.log10(SEED_RANGE_AU), (n, SEEDS)), axis=1)
    return {"f_g0": f_g0, "f_d0": f_dust(f_g0, feh), "tau_disk_yr": tau, "a0_au": a}


def annulus_solids(a_au, f_d, a_ice):
    """Solids (M⊕) in each seed's annulus, bounded by the geometric midpoints to its neighbours and
    by the seed range: ∫ 2π a Σ_d da with Σ_d of eq. 11 (∝ a^-3/2, stepped at the snow line)."""
    edges = np.sqrt(a_au[:, 1:] * a_au[:, :-1])
    lo = np.concatenate([np.full((len(a_au), 1), SEED_RANGE_AU[0]), edges], axis=1)
    hi = np.concatenate([edges, np.full((len(a_au), 1), SEED_RANGE_AU[1])], axis=1)

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
    """Integrate every seed of every disk. Returns arrays (systems × seeds): core and envelope mass
    (M⊕), final and formation radius (AU), whether the core is ice-rich, and the snow line."""
    a = disks["a0_au"].copy()
    tau = disks["tau_disk_yr"][:, None]
    f_g0, f_d = disks["f_g0"][:, None], disks["f_d0"][:, None]
    a_ice = float(snow_line_au(m_star_msun))
    solids_cap = annulus_solids(a, disks["f_d0"], a_ice)
    core = np.full(a.shape, SEED_MASS)
    env = np.zeros(a.shape)
    a_form = a.copy()
    gap = np.zeros(a.shape, bool)           # opened a gap: type II, no more gas
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
        # Solids, eq. 32: τ = K M^1/3, so M^1/3 rises by dt / 3K; capped at isolation (eq. 20)
        # and at the annulus's own solids
        k = core_accretion_time_yr(1.0, a, f_d, f_g, eta, m_star_msun)
        iso = np.minimum(isolation_mass(sigma_dust(a, f_d, a_ice), a, m_star_msun), solids_cap)
        growing = core < iso
        grown = (np.cbrt(m) + dt / (3 * k)) ** 3 - m
        new_core = np.where(growing, np.minimum(core + grown, iso), core)
        mdot_core = np.where(growing, (new_core - core) / np.maximum(dt, 1e-30), 0.0)
        a_form = np.where(new_core > core * (1 + 1e-9), a, a_form)
        core = new_core
        # Gas, eq. 34: τ_KH = 10⁹ M⁻³, so M⁻³ falls by 3 dt / 10⁹; truncated by eqs. 38 and 47
        m = core + env
        ceiling = np.minimum(gap_opening_mass(a, m_star_msun), disk_gas_mass_limit(f_g, a))
        accreting = ~gap & (core > critical_core_mass(mdot_core)) & (m < ceiling)
        left = m**-3 - 3 * dt / kelvin_helmholtz_time_yr(1.0)
        m_gas = np.where(left > 0, np.abs(left) ** (-1 / 3), np.inf)
        env = np.where(accreting, np.maximum(np.minimum(m_gas, ceiling) - core, env), env)
        m = core + env
        gap |= m >= gap_opening_mass(a, m_star_msun)
        # Migration: each rate is a power law ȧ ∝ a^n (type I n = -1/2; type II 1/2 or 0 where
        # eq. 70 binds), so a^(1-n) moves linearly in time; n is read off the rate itself
        here, nudged = (np.where(gap, type2_rate(r, m, f_g, tm, tau, m_star_msun, alpha),
                                 type1_rate(r, m, f_g, m_star_msun, c1)) for r in (a, a * 1.01))
        n_pow = np.clip(np.log(np.abs(nudged / here)) / np.log(1.01), -1.0, 0.9)
        e = 1 - n_pow
        moved = a**e + e * a ** -n_pow * here * dt
        edge = moved <= INNER_EDGE_AU**e
        new_a = np.where(edge, INNER_EDGE_AU, np.abs(moved) ** (1 / e))
        a = np.where(a > INNER_EDGE_AU, new_a, a)
    return {"core_mearth": core, "env_mearth": env, "a_au": a, "a_form_au": a_form,
            "ice_rich": a_form > a_ice, "a_ice_au": a_ice}


def merge_inner_edge(state: dict) -> dict:
    """All seeds parked at the inner edge of one disk merge into one planet, Ida & Lin 2008a §3.7's
    limiting case for close-in planets after the gas has gone; it keeps the formation radius of
    the most massive."""
    core, env = state["core_mearth"].copy(), state["env_mearth"].copy()
    a_form, a = state["a_form_au"].copy(), state["a_au"]
    edge = a <= INNER_EDGE_AU * (1 + 1e-9)
    total = core + env
    heaviest = np.argmax(np.where(edge, total, -1.0), axis=1)
    rows = np.flatnonzero(edge.sum(axis=1) > 1)
    for r in rows:   # only disks with more than one close-in seed, so the loop stays short
        k = heaviest[r]
        idx = np.flatnonzero(edge[r])
        core[r, k], env[r, k] = core[r, idx].sum(), env[r, idx].sum()
        others = idx[idx != k]
        core[r, others] = env[r, others] = 0.0
    return state | {"core_mearth": core, "env_mearth": env, "a_form_au": a_form,
                    "ice_rich": a_form > state["a_ice_au"]}


def planets(state: dict) -> dict:
    """The surviving planets (M_p ≥ M_MIN_PLANET) as flat arrays with their system index and
    class (classify.py)."""
    m = state["core_mearth"] + state["env_mearth"]
    keep = m >= M_MIN_PLANET
    system = np.nonzero(keep)[0]
    mass = m[keep]
    f_env = state["env_mearth"][keep] / mass
    ice = state["ice_rich"][keep]
    return {"system": system, "mass_mearth": mass, "f_env": f_env, "ice_rich": ice,
            "a_au": state["a_au"][keep], "a_form_au": state["a_form_au"][keep],
            "class": classify(mass, f_env, ice)}


def run_cell(m_star_msun: float, feh: float, n_systems: int, seed: int, **params) -> dict:
    """One cell of the grid: n_systems disks around one star, reproducible from `seed`."""
    p = DEFAULTS | params
    rng = np.random.default_rng(seed)
    disks = draw_disks(n_systems, m_star_msun, feh, rng, p["disk_mass_scaling"],
                       p["f_g_sigma_dex"], p["tau_disk_range_yr"])
    state = merge_inner_edge(evolve(disks, m_star_msun, p["c1"], p["alpha"], p["steps_per_dex"]))
    return {"disks": disks, "planets": planets(state), "n_systems": n_systems,
            "m_star_msun": m_star_msun, "feh": feh, "seed": seed, "params": p}

