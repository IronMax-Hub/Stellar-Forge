// Contract test: the app's own loader must parse contract/fixture.json.
// Its Python twin is tests/test_contract.py.

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parseDocument } from "../data/loader";
import { SCHEMA_VERSION } from "../data/types";

const fixture = (): Record<string, Record<string, unknown>> =>
  JSON.parse(readFileSync(new URL("../../../contract/fixture.json", import.meta.url), "utf8"));

describe("data contract", () => {
  it("parses the shared fixture", () => {
    const doc = parseDocument(fixture());
    expect(doc.meta.schema_version).toBe(SCHEMA_VERSION);
    expect(doc.track.rgb).toHaveLength(doc.track.age_yr.length);
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
    const wrongType = fixture();
    wrongType.track.age_yr = ["old"];
    expect(() => parseDocument(wrongType)).toThrow(/track\.age_yr\[0\]/);
    const uneven = fixture();
    (uneven.track.log_l_lsun as number[]).pop();
    expect(() => parseDocument(uneven)).toThrow(/track\.log_l_lsun/);
  });
});
