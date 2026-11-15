// Snapping the current star to a view's exported grid (currentStar.ts): selection only.

import { describe, expect, it } from "vitest";
import { indexAtAge, nearest } from "../currentStar";

describe("current star", () => {
  it("picks the nearest exported value, masses in log", () => {
    expect(nearest([-1, 0, 0.5], 0.2)).toBe(1);
    expect(nearest([0.2, 1.12, 1.5], 300, true)).toBe(2);
    // 1 and 4 are equally far from 2 in log, not linearly: the first wins a tie
    expect(nearest([1, 4], 2, true)).toBe(0);
    expect(nearest([1, 4], 2.6, true)).toBe(1);
    expect(nearest([1, 4], 2.4)).toBe(0);
  });

  it("finds the first exported age at or after the current age, else the last", () => {
    expect(indexAtAge([0, 10, 10, 20], 10)).toBe(1);
    expect(indexAtAge([0, 10, 20], 11)).toBe(2);
    expect(indexAtAge([0, 10, 20], 1e9)).toBe(2);
  });
});
