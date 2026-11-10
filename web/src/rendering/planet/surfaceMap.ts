// Surface map: a solid planet's present day as an equirectangular image the
// globe shader can read. Four channels:
//   R  elevation above sea level, km (negative under water)
//   G  temperature, K
//   B  moisture, 0–1
//   A  submerged: 1 where the ground holds water (open or frozen), 0 on land
// The coastline is where A crosses 0.5.
//
// Aion Forge built this image here from its own geography and climate. In
// Stellar-Forge the image arrives from Python; only its shape and its upload
// to the GPU remain.

import * as THREE from "three";

export const SURFACE_MAP_WIDTH = 512;
export const SURFACE_MAP_HEIGHT = 256;
export const SURFACE_MAP_CHANNELS = { elevationKm: 0, temperatureK: 1, moisture: 2, submerged: 3 } as const;

export interface SurfaceMapData {
  width: number;
  height: number;
  /** RGBA per texel, row 0 at the south (latitude −90°). */
  data: Float32Array;
}

/** Uploads a surface map as a half-float texture, filtered linearly and wrapping in longitude. */
export function surfaceMapTexture(map: SurfaceMapData): THREE.DataTexture {
  const half = new Uint16Array(map.data.length);
  for (let i = 0; i < map.data.length; i++) half[i] = THREE.DataUtils.toHalfFloat(map.data[i]);
  const texture = new THREE.DataTexture(half, map.width, map.height, THREE.RGBAFormat, THREE.HalfFloatType);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearFilter;
  texture.colorSpace = THREE.NoColorSpace;
  texture.needsUpdate = true;
  return texture;
}
