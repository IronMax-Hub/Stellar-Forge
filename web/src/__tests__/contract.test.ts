// Contract test: the app's own loader must parse contract/fixture.json.
// Its Python twin is tests/test_contract.py.

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parseDocument } from "../data/loader";
import { SCHEMA_VERSION } from "../data/types";

type Raw = Record<string, Record<string, unknown>>;
const fixture = (): Raw =>
  JSON.parse(readFileSync(new URL("../../../contract/fixture.json", import.meta.url), "utf8"));

describe("data contract", () => {
  it("parses the shared fixture", () => {
    const doc = parseDocument(fixture());
    expect(doc.meta.schema_version).toBe(SCHEMA_VERSION);
    const track = doc.grid!.tracks[0];
    expect(track.rgb).toHaveLength(track.age_yr.length);
    expect(doc.meta.references[0].doi).toMatch(/^10\./);
  });

  it("keeps every fixture field, so the loader and the fixture cannot drift apart", () => {
    expect(parseDocument(fixture())).toEqual(fixture());
  });

  it("rejects another schema version", () => {
    const raw = fixture();
    raw.meta.schema_version = SCHEMA_VERSION + 1;
    expect(() => parseDocument(raw)).toThrow(/schema_version/);
  });

  it("rejects a wrong field type and uneven arrays", () => {
    const firstTrack = (raw: Raw) => (raw.grid.tracks as Record<string, unknown>[])[0];
    const wrongType = fixture();
    firstTrack(wrongType).age_yr = ["old"];
    expect(() => parseDocument(wrongType)).toThrow(/tracks\[0\]\.age_yr\[0\]/);
    const uneven = fixture();
    (firstTrack(uneven).log_l_lsun as number[]).pop();
    expect(() => parseDocument(uneven)).toThrow(/tracks\[0\]\.log_l_lsun/);
  });

  it("accepts a remnant without mass and rejects an unknown remnant type", () => {
    const remnant = (raw: Raw) => (raw.grid.tracks as Record<string, Record<string, unknown>>[])[0].remnant;
    const none = fixture();
    Object.assign(remnant(none), { type: "not yet", mass_msun: null, radius_km: null, cooling: null });
    expect(parseDocument(none).grid!.tracks[0].remnant.mass_msun).toBeNull();
    const odd = fixture();
    remnant(odd).type = "quark star";
    expect(() => parseDocument(odd)).toThrow(/remnant\.type/);
  });

  it("reads a document with only an experiment, checks cell counts, and needs a block", () => {
    const raw = fixture();
    delete raw.grid;
    const doc = parseDocument(raw);
    expect(doc.grid).toBeUndefined();
    expect(doc.experiment!.panels[0].rows[0].labels[1]).toBe("track incomplete");
    const short = fixture();
    const panel = (short.experiment.panels as { rows: { values: unknown[] }[] }[])[0];
    panel.rows[0].values.pop();
    expect(() => parseDocument(short)).toThrow(/rows\[0\]\.values/);
    const empty = fixture();
    delete empty.grid;
    delete empty.experiment;
    delete empty.polytropes;
    delete empty.profiles;
    delete empty.population;
    delete empty.systems;
    delete empty.timeline;
    expect(() => parseDocument(empty)).toThrow(/grid, an experiment, a polytropes, a profiles, a population, a systems or a timeline/);
  });

  it("reads zero-age profiles, allows no MIST star, and rejects uneven arrays", () => {
    const profile = (raw: Raw) => (raw.profiles.models as Record<string, unknown>[])[0];
    expect(parseDocument(fixture()).profiles!.models[0].convective[1]).toBe(true);
    const noMist = fixture();
    profile(noMist).mist = null;
    expect(parseDocument(noMist).profiles!.models[0].mist).toBeNull();
    const uneven = fixture();
    (profile(uneven).convective as boolean[]).pop();
    expect(() => parseDocument(uneven)).toThrow(/models\[0\]\.convective/);
  });

  it("reads polytropes, allows n = 5's nulls, and rejects uneven profiles", () => {
    const doc = parseDocument(fixture());
    expect(doc.polytropes!.models[1].xi1).toBeNull();
    const uneven = fixture();
    ((uneven.polytropes.models as Record<string, number[]>[])[0].mass_frac).pop();
    expect(() => parseDocument(uneven)).toThrow(/models\[0\]\.mass_frac/);
  });

  it("reads the planet population and sample systems, and rejects bad counts and classes", () => {
    const doc = parseDocument(fixture());
    expect(doc.population!.cells[0].host_share["gas giant"]).toBe(0.25);
    expect(doc.systems!.systems[0].planets[1].class).toBe("gas giant");
    expect(doc.systems!.systems[1].planets).toHaveLength(0);
    const counts = fixture();
    ((counts.population.cells as Record<string, number[]>[])[0].systems_with_count).push(1);
    expect(() => parseDocument(counts)).toThrow(/systems_with_count/);
    const odd = fixture();
    ((odd.systems.systems as { planets: Record<string, unknown>[] }[])[0].planets[0]).class = "hot Jupiter";
    expect(() => parseDocument(odd)).toThrow(/planets\[0\]\.class/);
  });

  it("reads a timeline, allows undefined habitable-zone edges, and rejects bad orbit knots or events", () => {
    const planet = (raw: Raw) => ((raw.timeline.systems as { planets: Record<string, unknown>[] }[])[0].planets[0]);
    const tl = parseDocument(fixture()).timeline!;
    expect(tl.star.hz_inner_au[2]).toBeNull();
    expect(tl.systems[0].planets[0].events[0].kind).toBe("formed");
    expect(tl.systems[0].planets[0].orbit_pericentre_au).toHaveLength(tl.systems[0].planets[0].orbit_sample.length);
    const short = fixture();
    (planet(short).orbit_e as number[]).pop();
    expect(() => parseDocument(short)).toThrow(/orbit_e/);
    const late = fixture();
    planet(late).orbit_sample = [0, 1, 3];
    expect(() => parseDocument(late)).toThrow(/orbit_sample/);
    const odd = fixture();
    (planet(odd).events as { kind: string }[])[0].kind = "teleported";
    expect(() => parseDocument(odd)).toThrow(/events\[0\]\.kind/);
    const uneven = fixture();
    (uneven.timeline.star as { phase: string[] }).phase.pop();
    expect(() => parseDocument(uneven)).toThrow(/timeline\.star\.phase/);
  });
});
