// Turns parsed JSON into a typed document, checking every field's type.
// A wrong shape or schema version throws with the field's path, so a format
// change on the Python side fails loudly here instead of drawing nonsense.

import { PROVENANCES, SCHEMA_VERSION, TRACK_ARRAYS } from "./types";
import { CALIBRATIONS, CORES, EVENT_KINDS, FATES, PANEL_KINDS, PLANET_CLASSES, POLYTROPE_ARRAYS, PROFILE_ARRAYS, PROFILE_SCALARS, REMNANT_TYPES } from "./types";
import type { Calibration, Cooling, DataIndex, Experiment, PlanetClass, PlanetResult, PlanetSystem, Population, PopulationCell, Systems, Timeline, TimelinePlanet, TimelineStar, Grid, Meta, Panel, PanelKind, PanelRow, MistZams, Polytrope, Polytropes, Profile, Provenance, Reference, Remnant, RemnantType, Rgb, StellarDocument, Track, TrackArray } from "./types";

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
      radius_km: nullable(alt.radius_km, `${path}.alternative.radius_km`, number),
      how: string(alt.how, `${path}.alternative.how`),
      provenance: provenance(alt.provenance, `${path}.alternative.provenance`),
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

function parseMistZams(value: unknown, path: string): MistZams {
  const m = object(value, path);
  const keys = PROFILE_SCALARS.flatMap((k) => [k, `delta_${k}`]);
  return {
    provenance: provenance(m.provenance, `${path}.provenance`),
    ...Object.fromEntries(keys.map((k) => [k, number(m[k], `${path}.${k}`)])),
  } as MistZams;
}

function parseProfile(value: unknown, path: string): Profile {
  const p = object(value, path);
  const arrays = Object.fromEntries(PROFILE_ARRAYS.map((k) => [k, list(p[k], `${path}.${k}`, number)]));
  const convective = list(p.convective, `${path}.convective`, boolean);
  for (const [k, v] of [...Object.entries(arrays), ["convective", convective] as const]) {
    if (v.length !== arrays.r_frac.length) fail(`${path}.${k}`, `as long as ${path}.r_frac`);
  }
  const num = (k: string) => number(p[k], `${path}.${k}`);
  return {
    mass_msun: num("mass_msun"),
    feh: num("feh"),
    provenance: provenance(p.provenance, `${path}.provenance`),
    method: string(p.method, `${path}.method`),
    flags: list(p.flags, `${path}.flags`, string),
    x: num("x"),
    y: num("y"),
    z: num("z"),
    ...(Object.fromEntries(PROFILE_SCALARS.map((k) => [k, num(k)])) as Record<(typeof PROFILE_SCALARS)[number], number>),
    p_c_pa: num("p_c_pa"),
    energy_core_r_frac: num("energy_core_r_frac"),
    pp_share: num("pp_share"),
    mist: nullable(p.mist, `${path}.mist`, parseMistZams),
    ...(arrays as Record<(typeof PROFILE_ARRAYS)[number], number[]>),
    convective,
  };
}

function oneOf<T extends string>(allowed: readonly T[]): (value: unknown, path: string) => T {
  return (value, path) => {
    const v = string(value, path) as T;
    return allowed.includes(v) ? v : fail(path, `one of ${allowed.join(", ")}`);
  };
}
const planetClass = oneOf<PlanetClass>(PLANET_CLASSES);
const calibration = oneOf<Calibration>(CALIBRATIONS);

function integer(value: unknown, path: string): number {
  const n = number(value, path);
  return Number.isInteger(n) ? n : fail(path, "an integer");
}

function pair(value: unknown, path: string): [number, number] {
  const p = list(value, path, number);
  return p.length === 2 ? [p[0], p[1]] : fail(path, "[low, high]");
}

function parseCell(value: unknown, path: string): PopulationCell {
  const c = object(value, path);
  const share = record(c.host_share, `${path}.host_share`, number);
  for (const k of PLANET_CLASSES) if (!(k in share)) fail(`${path}.host_share`, `a share for ${k}`);
  const cell: PopulationCell = {
    m_star_msun: number(c.m_star_msun, `${path}.m_star_msun`),
    feh: number(c.feh, `${path}.feh`),
    n_systems: integer(c.n_systems, `${path}.n_systems`),
    seed: integer(c.seed, `${path}.seed`),
    calibration: calibration(c.calibration, `${path}.calibration`),
    provenance: provenance(c.provenance, `${path}.provenance`),
    host_share: share as Record<PlanetClass, number>,
    planets_per_star: number(c.planets_per_star, `${path}.planets_per_star`),
    systems_with_count: list(c.systems_with_count, `${path}.systems_with_count`, integer),
    a_ice_au: number(c.a_ice_au, `${path}.a_ice_au`),
    systems_file: string(c.systems_file, `${path}.systems_file`),
    timeline_file: string(c.timeline_file, `${path}.timeline_file`),
    flags: list(c.flags, `${path}.flags`, string),
  };
  if (cell.systems_with_count.reduce((a, b) => a + b, 0) !== cell.n_systems) fail(`${path}.systems_with_count`, "counts adding up to n_systems");
  return cell;
}

function parsePopulation(value: unknown): Population {
  const p = object(value, "population");
  const population: Population = {
    star_masses_msun: list(p.star_masses_msun, "population.star_masses_msun", number),
    feh_values: list(p.feh_values, "population.feh_values", number),
    classes: list(p.classes, "population.classes", planetClass),
    calibration_mass_msun: pair(p.calibration_mass_msun, "population.calibration_mass_msun"),
    calibration_feh: pair(p.calibration_feh, "population.calibration_feh"),
    cells: list(p.cells, "population.cells", parseCell),
    conclusions: list(p.conclusions, "population.conclusions", (v, q) => {
      const c = object(v, q);
      return { statement: string(c.statement, `${q}.statement`), label: calibration(c.label, `${q}.label`) };
    }),
  };
  if (population.cells.length !== population.star_masses_msun.length * population.feh_values.length) {
    fail("population.cells", "one cell per star mass and [Fe/H]");
  }
  return population;
}

function parsePlanet(value: unknown, path: string): PlanetResult {
  const p = object(value, path);
  const num = (k: string) => number(p[k], `${path}.${k}`);
  return {
    class: planetClass(p.class, `${path}.class`),
    mass_mearth: num("mass_mearth"),
    radius_rearth: num("radius_rearth"),
    a_au: num("a_au"),
    a_form_au: num("a_form_au"),
    e: num("e"),
    f_env: num("f_env"),
    core: oneOf(CORES)(p.core, `${path}.core`),
    provenance: provenance(p.provenance, `${path}.provenance`),
    radius_provenance: provenance(p.radius_provenance, `${path}.radius_provenance`),
  };
}

function parseSystem(value: unknown, path: string): PlanetSystem {
  const s = object(value, path);
  return {
    index: integer(s.index, `${path}.index`),
    f_g0: number(s.f_g0, `${path}.f_g0`),
    f_d0: number(s.f_d0, `${path}.f_d0`),
    tau_disk_yr: number(s.tau_disk_yr, `${path}.tau_disk_yr`),
    planets: list(s.planets, `${path}.planets`, parsePlanet),
  };
}

function parseSystems(value: unknown): Systems {
  const s = object(value, "systems");
  return {
    m_star_msun: number(s.m_star_msun, "systems.m_star_msun"),
    feh: number(s.feh, "systems.feh"),
    seed: integer(s.seed, "systems.seed"),
    calibration: calibration(s.calibration, "systems.calibration"),
    a_ice_au: number(s.a_ice_au, "systems.a_ice_au"),
    systems: list(s.systems, "systems.systems", parseSystem),
  };
}

function parseTimelineStar(value: unknown): TimelineStar {
  const s = object(value, "timeline.star");
  const nums = (k: string) => list(s[k], `timeline.star.${k}`, number);
  const edge = (k: string) => list(s[k], `timeline.star.${k}`, (v, p) => nullable(v, p, number));
  const star: TimelineStar = {
    provenance: provenance(s.provenance, "timeline.star.provenance"),
    method: string(s.method, "timeline.star.method"),
    ending: string(s.ending, "timeline.star.ending"),
    flags: list(s.flags, "timeline.star.flags", string),
    age_yr: nums("age_yr"), mass_msun: nums("mass_msun"), radius_au: nums("radius_au"),
    l_lsun: nums("l_lsun"), teff_k: nums("teff_k"),
    hz_inner_au: edge("hz_inner_au"), hz_outer_au: edge("hz_outer_au"),
    phase: list(s.phase, "timeline.star.phase", string),
    rgb: list(s.rgb, "timeline.star.rgb", rgb),
  };
  const n = star.age_yr.length;
  for (const k of ["mass_msun", "radius_au", "l_lsun", "teff_k", "hz_inner_au", "hz_outer_au", "phase", "rgb"] as const) {
    if (star[k].length !== n) fail(`timeline.star.${k}`, `one entry per age (${n})`);
  }
  return star;
}

function parseTimelinePlanet(value: unknown, path: string, ages: number): TimelinePlanet {
  const p = object(value, path);
  const num = (k: string) => number(p[k], `${path}.${k}`);
  const planet: TimelinePlanet = {
    name: nullable(p.name, `${path}.name`, string),
    class_at_formation: planetClass(p.class_at_formation, `${path}.class_at_formation`),
    class_final: planetClass(p.class_final, `${path}.class_final`),
    mass_mearth: num("mass_mearth"),
    final_mass_mearth: num("final_mass_mearth"),
    final_f_env: num("final_f_env"),
    orbit_sample: list(p.orbit_sample, `${path}.orbit_sample`, integer),
    orbit_a_au: list(p.orbit_a_au, `${path}.orbit_a_au`, number),
    orbit_e: list(p.orbit_e, `${path}.orbit_e`, number),
    orbit_pericentre_au: list(p.orbit_pericentre_au, `${path}.orbit_pericentre_au`, number),
    orbit_apocentre_au: list(p.orbit_apocentre_au, `${path}.orbit_apocentre_au`, number),
    e: num("e"),
    final_e: num("final_e"),
    fate: oneOf(FATES)(p.fate, `${path}.fate`),
    closest_approach_rstar: num("closest_approach_rstar"),
    deciding_phase: string(p.deciding_phase, `${path}.deciding_phase`),
    xuv_dose_earth: num("xuv_dose_earth"),
    shoreline: oneOf(["kept", "lost"] as const)(p.shoreline, `${path}.shoreline`),
    air_retained: num("air_retained"),
    events: list(p.events, `${path}.events`, (v, q) => {
      const e = object(v, q);
      return { age_yr: number(e.age_yr, `${q}.age_yr`), kind: oneOf(EVENT_KINDS)(e.kind, `${q}.kind`), detail: string(e.detail, `${q}.detail`) };
    }),
    flags: list(p.flags, `${path}.flags`, string),
    provenance: provenance(p.provenance, `${path}.provenance`),
  };
  const k = planet.orbit_sample;
  if (k.length === 0 || k.length !== planet.orbit_a_au.length || k.some((s, i) => s < 0 || s >= ages || (i > 0 && s <= k[i - 1]))) {
    fail(`${path}.orbit_sample`, "rising sample indices, one per orbit_a_au value");
  }
  for (const key of ["orbit_e", "orbit_pericentre_au", "orbit_apocentre_au"] as const) {
    if (planet[key].length !== k.length) fail(`${path}.${key}`, "one value per orbit_sample knot");
  }
  return planet;
}

function parseTimeline(value: unknown): Timeline {
  const t = object(value, "timeline");
  const star = parseTimelineStar(t.star);
  return {
    name: string(t.name, "timeline.name"),
    m_star_msun: number(t.m_star_msun, "timeline.m_star_msun"),
    feh: number(t.feh, "timeline.feh"),
    systems_file: nullable(t.systems_file, "timeline.systems_file", string),
    star,
    systems: list(t.systems, "timeline.systems", (v, q) => {
      const s = object(v, q);
      return {
        index: integer(s.index, `${q}.index`),
        planets: list(s.planets, `${q}.planets`, (pv, pq) => parseTimelinePlanet(pv, pq, star.age_yr.length)),
      };
    }),
  };
}

/** A typed document from parsed JSON; throws if any field is missing or of the wrong type. */
export function parseDocument(raw: unknown): StellarDocument {
  const doc = object(raw, "document");
  if ([doc.grid, doc.experiment, doc.polytropes, doc.profiles, doc.population, doc.systems, doc.timeline].every((b) => b === undefined)) {
    fail("document", "a grid, an experiment, a polytropes, a profiles, a population, a systems or a timeline block");
  }
  return {
    meta: parseMeta(doc.meta),
    ...(doc.grid !== undefined && { grid: parseGrid(doc.grid) }),
    ...(doc.experiment !== undefined && { experiment: parseExperiment(doc.experiment) }),
    ...(doc.polytropes !== undefined && { polytropes: parsePolytropes(doc.polytropes) }),
    ...(doc.profiles !== undefined && {
      profiles: { models: list(object(doc.profiles, "profiles").models, "profiles.models", parseProfile) },
    }),
    ...(doc.population !== undefined && { population: parsePopulation(doc.population) }),
    ...(doc.systems !== undefined && { systems: parseSystems(doc.systems) }),
    ...(doc.timeline !== undefined && { timeline: parseTimeline(doc.timeline) }),
  };
}

/** The data index. Its own schema_version is not checked here: an old index is itself reported. */
export function parseIndex(raw: unknown): DataIndex {
  const index = object(raw, "index");
  return {
    schema_version: integer(index.schema_version, "index.schema_version"),
    files: list(index.files, "index.files", (v, p) => {
      const f = object(v, p);
      return {
        file: string(f.file, `${p}.file`),
        schema_version: nullable(f.schema_version, `${p}.schema_version`, integer),
        target: string(f.target, `${p}.target`),
      };
    }),
  };
}

/** What the start-up banner says about the index, or null when every file is on this app's schema. */
export function staleDataMessage(index: DataIndex): string | null {
  const stale = index.files.filter((f) => f.schema_version !== SCHEMA_VERSION);
  if (stale.length === 0) return null;
  const targets = [...new Set(stale.map((f) => `make ${f.target}`))].sort().join(", ");
  const names = stale.slice(0, 3).map((f) => f.file).join(", ");
  const more = stale.length > 3 ? ` and ${stale.length - 3} more` : "";
  return `${stale.length} of ${index.files.length} data files are not on schema ${SCHEMA_VERSION}: ${names}${more}. Rebuild with ${targets}.`;
}
