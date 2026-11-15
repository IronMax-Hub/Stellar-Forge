// The current star and time, shared by Star Builder, Inside the Star, Planets and System Timeline
// (Phase 7). Each view shows the exported star nearest to the current one and says so when the two
// differ; picking a star or an age in any view sets it for all. Choosing the nearest exported value
// is selection, never interpolation: no view blends two files.

export interface CurrentStar {
  mass_msun: number;
  feh: number;
  age_yr: number;
}

export const SUN_TODAY: CurrentStar = { mass_msun: 1, feh: 0, age_yr: 4.57e9 };

export type View = "star" | "experiments" | "inside" | "planets" | "timeline";

/** What every star-aware view receives. `active` is false while its tab is hidden. */
export interface StarProps {
  star: CurrentStar;
  setStar: (star: CurrentStar) => void;
  show: (view: View) => void;
  active: boolean;
}

/** A hidden view is not redrawn; it catches up with the current star when its tab opens. */
export const skipWhileHidden = (_: unknown, next: { active: boolean }) => !next.active;

/** Index of the exported value nearest to x; masses are compared in log. */
export function nearest(values: number[], x: number, log = false): number {
  const d = (v: number) => Math.abs(log ? Math.log(v / x) : v - x);
  return values.reduce((best, v, k) => (d(v) < d(values[best]) ? k : best), 0);
}

/** Index of the first exported age at or after age_yr; the last index when the track ends sooner. */
export function indexAtAge(ages: number[], age_yr: number): number {
  const k = ages.findIndex((a) => a >= age_yr);
  return k < 0 ? ages.length - 1 : k;
}

export const fmtFeh = (feh: number) => `${feh > 0 ? "+" : ""}${feh}`;
