// The shape of an exported document: contract/README.md describes every field.
// Python writes these values; nothing here computes one.

/** Must equal SCHEMA_VERSION in stellarforge/__init__.py and the fixture's meta.schema_version. */
export const SCHEMA_VERSION = 3;

export type Provenance = "published" | "interpolated" | "derived" | "predicted";
export const PROVENANCES: readonly Provenance[] = ["published", "interpolated", "derived", "predicted"];

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

export interface StellarDocument {
  meta: Meta;
  grid: Grid;
}
