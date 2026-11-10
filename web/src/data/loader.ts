// Turns parsed JSON into a typed document, checking every field's type.
// A wrong shape or schema version throws with the field's path, so a format
// change on the Python side fails loudly here instead of drawing nonsense.

import { PROVENANCES, SCHEMA_VERSION } from "./types";
import type { Meta, Provenance, Reference, Rgb, StellarDocument, Track } from "./types";

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

function parseTrack(value: unknown): Track {
  const t = object(value, "track");
  const provenance = string(t.provenance, "track.provenance") as Provenance;
  if (!PROVENANCES.includes(provenance)) fail("track.provenance", `one of ${PROVENANCES.join(", ")}`);
  const track: Track = {
    provenance,
    flags: list(t.flags, "track.flags", string),
    age_yr: list(t.age_yr, "track.age_yr", number),
    log_l_lsun: list(t.log_l_lsun, "track.log_l_lsun", number),
    log_teff_k: list(t.log_teff_k, "track.log_teff_k", number),
    log_r_rsun: list(t.log_r_rsun, "track.log_r_rsun", number),
    rgb: list(t.rgb, "track.rgb", rgb),
  };
  const points = track.age_yr.length;
  for (const name of ["log_l_lsun", "log_teff_k", "log_r_rsun", "rgb"] as const) {
    if (track[name].length !== points) fail(`track.${name}`, `${points} entries long, like track.age_yr`);
  }
  return track;
}

/** A typed document from parsed JSON; throws if any field is missing or of the wrong type. */
export function parseDocument(raw: unknown): StellarDocument {
  const doc = object(raw, "document");
  return { meta: parseMeta(doc.meta), track: parseTrack(doc.track) };
}
