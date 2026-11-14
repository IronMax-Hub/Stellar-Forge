// The shape of an exported document: contract/README.md describes every field.
// Python writes these values; nothing here computes one.

/** Must equal SCHEMA_VERSION in stellarforge/__init__.py and the fixture's meta.schema_version. */
export const SCHEMA_VERSION = 9;

export type Provenance = "published" | "interpolated" | "substituted" | "derived" | "predicted";
export const PROVENANCES: readonly Provenance[] = ["published", "interpolated", "substituted", "derived", "predicted"];

export type Rgb = [number, number, number];

export interface Reference {
  key: string;
  citation: string;
  doi: string;
}

export interface Meta {
  schema_version: number;
  generator: { name: string; version: string; git_commit: string };
  dataset: string;
  models: Record<string, string>;
  inputs: Record<string, number>;
  seed: number | null;
  created: string;
  references: Reference[];
}

/** The arrays of a track, each one entry per point; `field_provenance` labels each. */
export const TRACK_ARRAYS = ["age_yr", "mass_now_msun", "log_l_lsun", "log_teff_k", "log_r_rsun", "phase", "rgb"] as const;
export type TrackArray = (typeof TRACK_ARRAYS)[number];

export interface Track {
  mass_msun: number;
  feh: number;
  method: string;
  provenance: Provenance;
  ending: string;
  flags: string[];
  /** MIST phase number (as a string key) -> name for this track */
  phase_names: Record<string, string>;
  field_provenance: Record<TrackArray, Provenance>;
  age_yr: number[];
  mass_now_msun: number[];
  log_l_lsun: number[];
  log_teff_k: number[];
  log_r_rsun: number[];
  phase: number[];
  rgb: Rgb[];
  remnant: Remnant;
}

export const REMNANT_TYPES = ["white dwarf", "neutron star", "black hole", "none", "not yet", "not predicted"] as const;
export type RemnantType = (typeof REMNANT_TYPES)[number];

export interface Cooling {
  cooling_age_yr: number[];
  log_l_lsun: number[];
  log_teff_k: number[];
  radius_km: number[];
}

/** What a star leaves behind; null fields mean no remnant or no value from MIST. */
export interface Remnant {
  type: RemnantType;
  mass_msun: number | null;
  radius_km: number | null;
  provenance: Provenance;
  prescription: string;
  how: string;
  alternative: { prescription: string; type: RemnantType; mass_msun: number | null };
  final_mass_msun: number | null;
  he_core_mass_msun: number | null;
  co_core_mass_msun: number | null;
  flags: string[];
  cooling: Cooling | null;
}

/** One [Fe/H] slice of the Star Builder grid; sliders snap to feh_values and mass_values_msun. */
export interface Grid {
  feh: number;
  feh_values: number[];
  mass_values_msun: number[];
  files: string[];
  tracks: Track[];
}

export const PANEL_KINDS = ["heatmap", "curves", "table"] as const;
export type PanelKind = (typeof PANEL_KINDS)[number];

/** A heatmap row, one curve or a table row: each cell is a number, a word (shown instead) or empty. */
export interface PanelRow {
  label: string;
  y: number | null;
  values: (number | null)[];
  labels: (string | null)[];
  provenance: (Provenance | null)[];
}

export interface Panel {
  title: string;
  kind: PanelKind;
  x_label: string;
  y_label: string;
  value_label: string;
  log_x: boolean;
  log_values: boolean;
  x_values: number[];
  columns: string[];
  rows: PanelRow[];
}

export interface Experiment {
  name: string;
  title: string;
  summary: string;
  panels: Panel[];
}

/** The profile arrays of a polytrope, all equally long, evenly spaced in radius. */
export const POLYTROPE_ARRAYS = ["radius_frac", "xi", "theta", "mass_frac", "density_frac", "pressure_frac"] as const;
export type PolytropeArray = (typeof POLYTROPE_ARRAYS)[number];

/** One Lane-Emden polytrope; null fields are for n = 5, which has no surface. */
export interface Polytrope extends Record<PolytropeArray, number[]> {
  n: number;
  provenance: Provenance;
  flags: string[];
  xi1: number | null;
  mass_constant: number;
  density_concentration: number | null;
  sun_rho_c_kg_m3: number | null;
  sun_p_c_pa: number | null;
  sun_t_c_k: number | null;
}

/** Every exported polytrope; the n slider snaps to n_values. */
export interface Polytropes {
  n_values: number[];
  models: Polytrope[];
}

/** The numeric profile arrays of a zero-age star, centre to surface; `convective` is the flag array. */
export const PROFILE_ARRAYS = ["r_frac", "m_frac", "l_frac", "t_frac", "rho_frac", "p_frac", "eps_pp_w_kg", "eps_cno_w_kg", "kappa_m2_kg", "nabla", "nabla_ad", "nabla_rad"] as const;
export type ProfileArray = (typeof PROFILE_ARRAYS)[number];
export const PROFILE_SCALARS = ["log_l_lsun", "log_r_rsun", "log_teff_k", "log_t_c_k", "log_rho_c_kg_m3"] as const;
export type ProfileScalar = (typeof PROFILE_SCALARS)[number];

/** MIST's zero-age star, and model minus MIST (`delta_<name>`, dex). */
export type MistZams = { provenance: Provenance } & Record<ProfileScalar | `delta_${ProfileScalar}`, number>;

/** One star's zero-age structure from the centre to the surface. */
export interface Profile extends Record<ProfileArray, number[]>, Record<ProfileScalar, number> {
  mass_msun: number;
  feh: number;
  provenance: Provenance;
  method: string;
  flags: string[];
  x: number;
  y: number;
  z: number;
  p_c_pa: number;
  energy_core_r_frac: number;
  pp_share: number;
  mist: MistZams | null;
  convective: boolean[];
}

export const PLANET_CLASSES = ["gas giant", "ice giant", "sub-Neptune", "super-Earth", "terrestrial"] as const;
export type PlanetClass = (typeof PLANET_CLASSES)[number];
export const CALIBRATIONS = ["observational constraint", "prediction", "parameter-sensitive", "extrapolation"] as const;
export type Calibration = (typeof CALIBRATIONS)[number];
export const CORES = ["ice-rich", "rock-dominated"] as const;
export type Core = (typeof CORES)[number];

/** One star mass and [Fe/H] of the planet grid. */
export interface PopulationCell {
  m_star_msun: number;
  feh: number;
  n_systems: number;
  seed: number;
  calibration: Calibration;
  provenance: Provenance;
  /** class -> share of systems with at least one planet of that class */
  host_share: Record<PlanetClass, number>;
  planets_per_star: number;
  /** entry k: systems with exactly k planets */
  systems_with_count: number[];
  a_ice_au: number;
  /** relative to the data folder */
  systems_file: string;
  /** validity warnings, such as survey checks the model fails */
  flags: string[];
}

/** The planet grid; the selectors snap to star_masses_msun and feh_values. */
export interface Population {
  star_masses_msun: number[];
  feh_values: number[];
  classes: PlanetClass[];
  calibration_mass_msun: [number, number];
  calibration_feh: [number, number];
  /** [Fe/H]-major: all masses of the first [Fe/H] first */
  cells: PopulationCell[];
  conclusions: { statement: string; label: Calibration }[];
}

export interface PlanetResult {
  class: PlanetClass;
  mass_mearth: number;
  radius_rearth: number;
  a_au: number;
  a_form_au: number;
  f_env: number;
  core: Core;
  provenance: Provenance;
  radius_provenance: Provenance;
}

export interface PlanetSystem {
  index: number;
  f_g0: number;
  f_d0: number;
  tau_disk_yr: number;
  /** from the inside out */
  planets: PlanetResult[];
}

/** One cell's sample systems. */
export interface Systems {
  m_star_msun: number;
  feh: number;
  seed: number;
  calibration: Calibration;
  a_ice_au: number;
  systems: PlanetSystem[];
}

/** meta plus the blocks a file carries: a grid, an experiment, the polytropes, zero-age profiles,
 * a planet population or one cell's sample systems. */
export interface StellarDocument {
  meta: Meta;
  grid?: Grid;
  experiment?: Experiment;
  polytropes?: Polytropes;
  profiles?: { models: Profile[] };
  population?: Population;
  systems?: Systems;
}
