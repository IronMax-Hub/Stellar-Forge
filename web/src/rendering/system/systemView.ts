// What the 3D system view draws (SystemView3D.tsx): the host star as a source of
// light, the planets' orbits as ellipses, the starlight the planets are lit by,
// and where a planet is along its ellipse.
//
// How:
// - The star: a sphere whose brightness falls toward its edge (limb darkening,
//   as the Sun's does), in its display colour (starColour.ts) and outside the
//   tone mapping so the colour is not washed to white, inside a restrained
//   additive glow in the same colour.
// - Orbits: one-pixel ellipses, the same width at every zoom, through the
//   exported a and e.
// - Light: a point light at the star in its colour (no fall-off: planets are drawn
//   enlarged, far from true scale, so a true fall-off would only mislead), and a
//   faint fill so night sides are not pure black.
// - Motion, animation only (Phase 7 step 4): each planet goes round at its period
//   relative to the others (P ∝ a^1.5), compressed so the innermost goes round once
//   a minute, and is placed along its ellipse by Kepler's equation. Neither is a
//   result: the files say nothing about where a planet is "now".
//
// Assumptions and limits: planet sizes are not to scale.
//
// Presentation only: it reads exported values and never computes a result.

import * as THREE from "three";

// Limb darkening: brightness at the edge as a share of the centre's (the Sun's is about 0.4 in visible light)
const LIMB_BRIGHTNESS = 0.45;
// The star's centre is drawn at its display colour, outside the tone mapping, which would wash it toward
// white (at 1.4 and tone-mapped it once saturated to white); its darker limb still shows
const STAR_SURFACE_BRIGHTNESS = 1;
// How far the star's surface is lightened toward white, so its centre reads as hot (it was 0.35)
const STAR_SURFACE_WHITENING = 0.12;
const STAR_SEGMENTS = 64;
// The glow sprite spans this many star radii, and its texture this many texels
const GLOW_RADII = 7;
const GLOW_TEXTURE_SIZE = 128;
const GLOW_OPACITY = 0.6;

/** Orbits are drawn at this many scene units per AU. */
export const SYSTEM_UNITS_PER_AU = 2.5;

const ORBIT_SEGMENTS = 256;

/** Starlight on the planets, as the planet view's at Earth's flux (PlanetView.ts). */
export const SYSTEM_STARLIGHT_INTENSITY = 2.6;
const NIGHT_FILL_INTENSITY = 0.03;

const STAR_VERTEX = /* glsl */`
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vec4 view = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-view.xyz);
    gl_Position = projectionMatrix * view;
  }
`;

const STAR_FRAGMENT = /* glsl */`
  uniform vec3 starColor;
  uniform float brightness;
  uniform float limbBrightness;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    float mu = clamp(dot(normalize(vNormal), normalize(vView)), 0.0, 1.0);
    float limb = mix(limbBrightness, 1.0, mu);
    gl_FragColor = vec4(starColor * brightness * limb, 1.0);
    #include <colorspace_fragment>
  }
`;

/** A soft radial glow, white; tinted by the sprite's colour. */
function glowTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = GLOW_TEXTURE_SIZE;
  const ctx = canvas.getContext("2d")!;
  const image = ctx.createImageData(GLOW_TEXTURE_SIZE, GLOW_TEXTURE_SIZE);
  const half = GLOW_TEXTURE_SIZE / 2;
  for (let y = 0; y < GLOW_TEXTURE_SIZE; y++) {
    for (let x = 0; x < GLOW_TEXTURE_SIZE; x++) {
      // Distance from the centre in star radii (the sprite spans GLOW_RADII of them)
      const r = Math.hypot(x + 0.5 - half, y + 0.5 - half) / half * (GLOW_RADII / 2);
      const fade = Math.max(0, 1 - r / (GLOW_RADII / 2));
      // Light scattered around a bright source falls off roughly as 1/r², softened at the core
      const alpha = Math.min(1, 0.9 / (1 + r * r)) * fade * fade;
      const i = (y * GLOW_TEXTURE_SIZE + x) * 4;
      image.data[i] = image.data[i + 1] = image.data[i + 2] = 255;
      image.data[i + 3] = Math.round(alpha * 255);
    }
  }
  ctx.putImageData(image, 0, 0);
  return new THREE.CanvasTexture(canvas);
}

/** The host star: a limb-darkened sphere of this radius inside its glow. */
export function hostStarObject(color: THREE.Color, radius: number): THREE.Group {
  const group = new THREE.Group();
  const surface = new THREE.Mesh(
    new THREE.SphereGeometry(radius, STAR_SEGMENTS, STAR_SEGMENTS / 2),
    new THREE.ShaderMaterial({
      vertexShader: STAR_VERTEX,
      fragmentShader: STAR_FRAGMENT,
      uniforms: {
        starColor: { value: color.clone().lerp(new THREE.Color(1, 1, 1), STAR_SURFACE_WHITENING) },
        brightness: { value: STAR_SURFACE_BRIGHTNESS },
        limbBrightness: { value: LIMB_BRIGHTNESS },
      },
    }),
  );
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture(), color, transparent: true, opacity: GLOW_OPACITY,
    blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false,
  }));
  glow.scale.setScalar(radius * GLOW_RADII);
  group.add(surface, glow);
  return group;
}

/** The eccentric anomaly E for a mean anomaly M (Kepler's equation M = E − e sin E, by Newton's method). */
export function eccentricAnomaly(meanAnomaly: number, e: number): number {
  let E = e < 0.8 ? meanAnomaly : Math.PI;
  for (let i = 0; i < 30; i++) {
    const step = (E - e * Math.sin(E) - meanAnomaly) / (1 - e * Math.cos(E));
    E -= step;
    if (Math.abs(step) < 1e-12) break;
  }
  return E;
}

/** Where a body on a Kepler path is, x and z in its group, at this mean anomaly. */
export function keplerPlace(path: KeplerPath, meanAnomaly: number): [number, number] {
  const E = eccentricAnomaly(meanAnomaly, path.e);
  // Relative position in the orbit's own frame, periapsis along +x' (the focus at the origin)
  const xo = path.a * (Math.cos(E) - path.e);
  const yo = path.a * Math.sqrt(1 - path.e * path.e) * Math.sin(E);
  const c = Math.cos(path.periapsis);
  const s = Math.sin(path.periapsis);
  // Turned by the periapsis angle about +y, then scaled by the body's share
  return [path.share * (xo * c - yo * s), -path.share * (xo * s + yo * c)];
}

/** A Kepler path drawn whole: a one-pixel ellipse in the x–z plane. */
export function keplerLine(path: KeplerPath, colour: THREE.ColorRepresentation, opacity: number): THREE.LineLoop {
  const points = new Float32Array(ORBIT_SEGMENTS * 3);
  for (let i = 0; i < ORBIT_SEGMENTS; i++) {
    // Even steps in eccentric anomaly, so the ellipse is smooth at both ends
    const E = (i / ORBIT_SEGMENTS) * 2 * Math.PI;
    const M = E - path.e * Math.sin(E);
    const [x, z] = keplerPlace(path, M);
    points[i * 3] = x;
    points[i * 3 + 2] = z;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
  return new THREE.LineLoop(geometry, new THREE.LineBasicMaterial({ color: colour, transparent: true, opacity, depthWrite: false }));
}

/** The starlight planets are lit by, from the star at the group's origin, and the night-side fill. */
export function systemLights(color: THREE.Color, intensity = SYSTEM_STARLIGHT_INTENSITY): THREE.Light[] {
  return [
    new THREE.PointLight(color, intensity, 0, 0),
    new THREE.AmbientLight(0xffffff, NIGHT_FILL_INTENSITY),
  ];
}

/** Frees a system group's GPU resources, textures included. */
export function disposeSystemGroup(group: THREE.Object3D): void {
  group.traverse((object) => {
    const mesh = object as THREE.Mesh;
    mesh.geometry?.dispose();
    const materials = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
    for (const material of materials) {
      (material as THREE.SpriteMaterial).map?.dispose();
      material.dispose();
    }
  });
}

// ── Orbital motion (animation only) ─────────────────────────────────────────

/** The innermost planet goes round once in this many seconds on screen (owner decision). */
export const INNER_ORBIT_SECONDS = 60;

/** Seconds on screen for one orbit of this radius, when the innermost of radius `innermost` takes INNER_ORBIT_SECONDS. */
export function secondsPerOrbit(radius: number, innermost: number): number {
  return INNER_ORBIT_SECONDS * Math.pow(radius / innermost, 1.5);
}

/**
 * A body on a Kepler ellipse. The orbit has semi-major axis `a` (scene units), eccentricity `e`
 * and its closest approach toward `periapsis` (radians about +y); the body sits at `share` of the
 * relative position (1 for a planet round its star).
 */
export interface KeplerPath {
  a: number;
  e: number;
  share: number;
  periapsis: number;
}
