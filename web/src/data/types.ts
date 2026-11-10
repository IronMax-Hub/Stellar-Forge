// The shape of an exported document: contract/README.md describes every field.
// Python writes these values; nothing here computes one.

/** Must equal SCHEMA_VERSION in stellarforge/__init__.py and the fixture's meta.schema_version. */
export const SCHEMA_VERSION = 1;

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

export interface Track {
  provenance: Provenance;
  flags: string[];
  age_yr: number[];
  log_l_lsun: number[];
  log_teff_k: number[];
  log_r_rsun: number[];
  rgb: Rgb[];
}

export interface StellarDocument {
  meta: Meta;
  track: Track;
}
