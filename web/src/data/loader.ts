// Turns parsed JSON into a typed document, checking every field's type.
// A wrong shape or schema version throws with the field's path, so a format
// change on the Python side fails loudly here instead of drawing nonsense.

import { PROVENANCES, SCHEMA_VERSION, TRACK_ARRAYS } from "./types";
import { PANEL_KINDS, POLYTROPE_ARRAYS, REMNANT_TYPES } from "./types";
import type { Cooling, Experiment, Grid, Meta, Panel, PanelKind, PanelRow, Polytrope, Polytropes, Provenance, Reference, Remnant, RemnantType, Rgb, StellarDocument, Track, TrackArray } from "./types";

type Json = Record<string, unknown>;

function fail(path: string, expected: string): never {
  throw new Error(`Contract: ${path} should be ${expected}`);
}

function object(value: unknown, path: string): Json {
  if (typeof value !== "object" || value === null || Array.isArray(value)) fail(path, "an object");
  return value as Json;
}

function string(value: unknown, path: string): string {
  return typeof value === "string" ? value : fail(path, "a string");
}

function number(value: unknown, path: string): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fail(path, "a finite number");
}

function list<T>(value: unknown, path: string, item: (v: unknown, p: string) => T): T[] {
  if (!Array.isArray(value)) fail(path, "a list");
  return value.map((v, i) => item(v, `${path}[${i}]`));
}

function record<T>(value: unknown, path: string, item: (v: unknown, p: string) => T): Record<string, T> {
  return Object.fromEntries(Object.entries(object(value, path)).map(([k, v]) => [k, item(v, `${path}.${k}`)]));
}

function rgb(value: unknown, path: string): Rgb {
  const channels = list(value, path, number);
  if (channels.length !== 3 || channels.some((c) => c < 0 || c > 1)) fail(path, "three channels from 0 to 1");
  return channels as Rgb;
}

function reference(value: unknown, path: string): Reference {
  const r = object(value, path);
  return { key: string(r.key, `${path}.key`), citation: string(r.citation, `${path}.citation`), doi: string(r.doi, `${path}.doi`) };
}

function parseMeta(value: unknown): Meta {
  const m = object(value, "meta");
  const version = number(m.schema_version, "meta.schema_version");
  if (version !== SCHEMA_VERSION) fail("meta.schema_version", `${SCHEMA_VERSION}, got ${version}`);
  const g = object(m.generator, "meta.generator");
  return {
    schema_version: version,
    generator: {
      name: string(g.name, "meta.generator.name"),
      version: string(g.version, "meta.generator.version"),
      git_commit: string(g.git_commit, "meta.generator.git_commit"),
    },
    dataset: string(m.dataset, "meta.dataset"),
    models: record(m.models, "meta.models", string),
    inputs: record(m.inputs, "meta.inputs", number),
    seed: m.seed === null ? null : number(m.seed, "meta.seed"),
    created: string(m.created, "meta.created"),
    references: list(m.references, "meta.references", reference),
  };
}

function provenance(value: unknown, path: string): Provenance {
  const p = string(value, path) as Provenance;
  return PROVENANCES.includes(p) ? p : fail(path, `one of ${PROVENANCES.join(", ")}`);
}

function nullable<T>(value: unknown, path: string, item: (v: unknown, p: string) => T): T | null {
  return value === null ? null : item(value, path);
}

function remnantType(value: unknown, path: string): RemnantType {
  const t = string(value, path) as RemnantType;
  return REMNANT_TYPES.includes(t) ? t : fail(path, `one of ${REMNANT_TYPES.join(", ")}`);
}

function parseCooling(value: unknown, path: string): Cooling {
  const c = object(value, path);
  const cooling: Cooling = {
    cooling_age_yr: list(c.cooling_age_yr, `${path}.cooling_age_yr`, number),
    log_l_lsun: list(c.log_l_lsun, `${path}.log_l_lsun`, number),
    log_teff_k: list(c.log_teff_k, `${path}.log_teff_k`, number),
    radius_km: list(c.radius_km, `${path}.radius_km`, number),
  };
  for (const name of ["log_l_lsun", "log_teff_k", "radius_km"] as const) {
    if (cooling[name].length !== cooling.cooling_age_yr.length) fail(`${path}.${name}`, "as long as cooling_age_yr");
  }
  return cooling;
}

function parseRemnant(value: unknown, path: string): Remnant {
  const r = object(value, path);
  const alt = object(r.alternative, `${path}.alternative`);
  return {
    type: remnantType(r.type, `${path}.type`),
    mass_msun: nullable(r.mass_msun, `${path}.mass_msun`, number),
    radius_km: nullable(r.radius_km, `${path}.radius_km`, number),
    provenance: provenance(r.provenance, `${path}.provenance`),
    prescription: string(r.prescription, `${path}.prescription`),
    how: string(r.how, `${path}.how`),
    alternative: {
      prescription: string(alt.prescription, `${path}.alternative.prescription`),
      type: remnantType(alt.type, `${path}.alternative.type`),
      mass_msun: nullable(alt.mass_msun, `${path}.alternative.mass_msun`, number),
    },
    final_mass_msun: nullable(r.final_mass_msun, `${path}.final_mass_msun`, number),
    he_core_mass_msun: nullable(r.he_core_mass_msun, `${path}.he_core_mass_msun`, number),
    co_core_mass_msun: nullable(r.co_core_mass_msun, `${path}.co_core_mass_msun`, number),
    flags: list(r.flags, `${path}.flags`, string),
    cooling: nullable(r.cooling, `${path}.cooling`, parseCooling),
  };
}

function parseTrack(value: unknown, path: string): Track {
  const t = object(value, path);
  const fp = object(t.field_provenance, `${path}.field_provenance`);
  const track: Track = {
    mass_msun: number(t.mass_msun, `${path}.mass_msun`),
    feh: number(t.feh, `${path}.feh`),
    method: string(t.method, `${path}.method`),
    provenance: provenance(t.provenance, `${path}.provenance`),
    ending: string(t.ending, `${path}.ending`),
    flags: list(t.flags, `${path}.flags`, string),
    phase_names: record(t.phase_names, `${path}.phase_names`, string),
    field_provenance: Object.fromEntries(
      TRACK_ARRAYS.map((k) => [k, provenance(fp[k], `${path}.field_provenance.${k}`)]),
    ) as Record<TrackArray, Provenance>,
    age_yr: list(t.age_yr, `${path}.age_yr`, number),
    mass_now_msun: list(t.mass_now_msun, `${path}.mass_now_msun`, number),
    log_l_lsun: list(t.log_l_lsun, `${path}.log_l_lsun`, number),
    log_teff_k: list(t.log_teff_k, `${path}.log_teff_k`, number),
    log_r_rsun: list(t.log_r_rsun, `${path}.log_r_rsun`, number),
    phase: list(t.phase, `${path}.phase`, number),
    rgb: list(t.rgb, `${path}.rgb`, rgb),
    remnant: parseRemnant(t.remnant, `${path}.remnant`),
  };
  const points = track.age_yr.length;
  for (const name of TRACK_ARRAYS) {
    if (track[name].length !== points) fail(`${path}.${name}`, `${points} entries long, like ${path}.age_yr`);
  }
  return track;
}

function parseGrid(value: unknown): Grid {
  const g = object(value, "grid");
  const grid: Grid = {
    feh: number(g.feh, "grid.feh"),
    feh_values: list(g.feh_values, "grid.feh_values", number),
    mass_values_msun: list(g.mass_values_msun, "grid.mass_values_msun", number),
    files: list(g.files, "grid.files", string),
    tracks: list(g.tracks, "grid.tracks", parseTrack),
  };
  if (grid.files.length !== grid.feh_values.length) fail("grid.files", "one file per grid.feh_values entry");
  if (grid.tracks.length !== grid.mass_values_msun.length) fail("grid.tracks", "one track per grid.mass_values_msun entry");
  return grid;
}

function boolean(value: unknown, path: string): boolean {
  return typeof value === "boolean" ? value : fail(path, "true or false");
}

function parseRow(value: unknown, path: string, width: number): PanelRow {
  const r = object(value, path);
  const row: PanelRow = {
    label: string(r.label, `${path}.label`),
    y: nullable(r.y, `${path}.y`, number),
    values: list(r.values, `${path}.values`, (v, p) => nullable(v, p, number)),
    labels: list(r.labels, `${path}.labels`, (v, p) => nullable(v, p, string)),
    provenance: list(r.provenance, `${path}.provenance`, (v, p) => nullable(v, p, provenance)),
  };
  for (const name of ["values", "labels", "provenance"] as const) {
    if (row[name].length !== width) fail(`${path}.${name}`, `${width} cells long`);
  }
  return row;
}

function parsePanel(value: unknown, path: string): Panel {
  const p = object(value, path);
  const kind = string(p.kind, `${path}.kind`) as PanelKind;
  if (!PANEL_KINDS.includes(kind)) fail(`${path}.kind`, `one of ${PANEL_KINDS.join(", ")}`);
  const xValues = list(p.x_values, `${path}.x_values`, number);
  const columns = list(p.columns, `${path}.columns`, string);
  const width = kind === "table" ? columns.length : xValues.length;
  return {
    title: string(p.title, `${path}.title`),
    kind,
    x_label: string(p.x_label, `${path}.x_label`),
    y_label: string(p.y_label, `${path}.y_label`),
    value_label: string(p.value_label, `${path}.value_label`),
    log_x: boolean(p.log_x, `${path}.log_x`),
    log_values: boolean(p.log_values, `${path}.log_values`),
    x_values: xValues,
    columns,
    rows: list(p.rows, `${path}.rows`, (v, q) => parseRow(v, q, width)),
  };
}

function parseExperiment(value: unknown): Experiment {
  const e = object(value, "experiment");
  return {
    name: string(e.name, "experiment.name"),
    title: string(e.title, "experiment.title"),
    summary: string(e.summary, "experiment.summary"),
    panels: list(e.panels, "experiment.panels", parsePanel),
  };
}

function parsePolytrope(value: unknown, path: string): Polytrope {
  const m = object(value, path);
  const arrays = Object.fromEntries(POLYTROPE_ARRAYS.map((k) => [k, list(m[k], `${path}.${k}`, number)]));
  for (const k of POLYTROPE_ARRAYS) {
    if (arrays[k].length !== arrays.radius_frac.length) fail(`${path}.${k}`, `as long as ${path}.radius_frac`);
  }
  const maybe = (k: string) => nullable(m[k], `${path}.${k}`, number);
  return {
    n: number(m.n, `${path}.n`),
    provenance: provenance(m.provenance, `${path}.provenance`),
    flags: list(m.flags, `${path}.flags`, string),
    xi1: maybe("xi1"),
    mass_constant: number(m.mass_constant, `${path}.mass_constant`),
    density_concentration: maybe("density_concentration"),
    sun_rho_c_kg_m3: maybe("sun_rho_c_kg_m3"),
    sun_p_c_pa: maybe("sun_p_c_pa"),
    sun_t_c_k: maybe("sun_t_c_k"),
    ...(arrays as Record<(typeof POLYTROPE_ARRAYS)[number], number[]>),
  };
}

function parsePolytropes(value: unknown): Polytropes {
  const p = object(value, "polytropes");
  const polytropes: Polytropes = {
    n_values: list(p.n_values, "polytropes.n_values", number),
    models: list(p.models, "polytropes.models", parsePolytrope),
  };
  if (polytropes.models.length !== polytropes.n_values.length) fail("polytropes.models", "one model per polytropes.n_values entry");
  return polytropes;
}

/** A typed document from parsed JSON; throws if any field is missing or of the wrong type. */
export function parseDocument(raw: unknown): StellarDocument {
  const doc = object(raw, "document");
  if (doc.grid === undefined && doc.experiment === undefined && doc.polytropes === undefined) {
    fail("document", "a grid, an experiment or a polytropes block");
  }
  return {
    meta: parseMeta(doc.meta),
    ...(doc.grid !== undefined && { grid: parseGrid(doc.grid) }),
    ...(doc.experiment !== undefined && { experiment: parseExperiment(doc.experiment) }),
    ...(doc.polytropes !== undefined && { polytropes: parsePolytropes(doc.polytropes) }),
  };
}
