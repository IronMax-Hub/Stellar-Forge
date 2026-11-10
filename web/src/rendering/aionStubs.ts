// Stand-ins for the Aion Forge simulation types that the copied views read.
//
// Aion Forge computed these values in TypeScript. Here every value arrives from
// Python in the exported JSON (ground rule 2), so these are plain data shapes
// with no formulas. They are provisional: Phases 2, 6 and 7 replace them with
// the contract's `remnant`, `system` and `appearance` blocks.

import type { SurfaceMapData } from "./planet/surfaceMap";

export type Rgb = [number, number, number];

export type PlanetType =
  | "rocky" | "ocean" | "ice" | "desert" | "gas-giant" | "ice-giant" | "sub-neptune" | "lava" | "rogue";

/** Flat colours for planets drawn without a surface (presentation only). */
export const PLANET_COLORS: Record<PlanetType, Rgb> = {
  rocky:       [0.55, 0.42, 0.30],
  ocean:       [0.15, 0.45, 0.80],
  ice:         [0.75, 0.88, 0.95],
  desert:      [0.82, 0.65, 0.30],
  "gas-giant": [0.70, 0.55, 0.35],
  "ice-giant": [0.45, 0.65, 0.85],
  "sub-neptune": [0.55, 0.72, 0.78],
  lava:        [0.90, 0.25, 0.05],
  rogue:       [0.20, 0.18, 0.22],
};

/** A world's place in its system; seeds its visual random stream. */
export interface BodyRef {
  hostStarId: number;
  /** The planet's index in its system; for a moon, its planet's. */
  id: number;
  moonIndex?: number;
}

const MOON_TAG = 0x4d4f4f4e;

/** The stream-key parts of a world, so each world's visual draws are its own. */
export function bodyKey(body: BodyRef): number[] {
  return body.moonIndex === undefined
    ? [body.hostStarId, body.id]
    : [body.hostStarId, body.id, MOON_TAG, body.moonIndex];
}

export interface Moon {
  /** Radius, Earth radii. */
  size: number;
  /** Orbit, in radii of its planet. */
  orbitPlanetRadii: number;
}

export interface Planet extends BodyRef {
  key: string;
  type: PlanetType;
  /** Radius, Earth radii. */
  size: number;
  /** Temperature, K: surface for solid planets, cloud tops for giants. */
  temperature: number;
  /** The colour its own heat glows with, sRGB 0–1. */
  glowRgb: Rgb;
  /** Orbit, AU. */
  orbitalRadius: number;
  /** Null for giants. */
  surface: { pressureBar: number } | null;
  moons: Moon[];
}

export interface Star {
  /** The star's true colour, sRGB 0–1. */
  rgb: Rgb;
  /** Its light in the red, green and blue channels, brightest channel 1. */
  spectrumRgb: Rgb;
}

/** What a solid planet's globe is baked from. */
export interface SolidWorld {
  surfaceMap: SurfaceMapData;
  /** 0–1: how much of frozen land is snow. */
  wetness: number;
  /** Below this its water is ice, K. */
  freezingK: number;
  /** Water's boiling point under its air, K. */
  boilingK: number;
  /** 0–1: share of the sky thick air clouds over. */
  overcast: number;
}

export interface PlanetPhysics {
  rotationPeriodHours: number;
  axialTiltDeg: number;
  tidallyLocked: boolean;
}

/** "none": an isolated stellar black hole with no gas, so only the lensed sky shows. */
export type AccretionMode = "thin-disc" | "hot-flow" | "none";
export type GalaxyType = "spiral" | "elliptical" | "irregular";

export interface CentralBlackHole {
  /** Event-horizon radius, km. */
  horizonRadiusKm: number;
  accretionMode: AccretionMode;
  /** Its gas's hottest temperature, K. */
  discPeakTemperatureK: number;
}
