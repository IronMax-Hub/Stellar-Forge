// A star's colour as the views draw it.
//
// Why it exists: a blackbody's true colour is pale. Seen as a disc or a point,
// a K star and a G star both read as white, so star types are hard to tell
// apart. The views keep each star's true hue and push it away from white by a
// fixed factor, so the classes separate: M red-orange, K orange, G yellow-white,
// F and A white, B and O blue. The interface says the colours are boosted.
//
// How: each channel's distance below the brightest channel is multiplied by
// STAR_SATURATION_BOOST, so the hue stays and the brightest channel is kept.
//
// Presentation only. The true colour (`rgb`, sRGB 0–1) is computed in Python
// and arrives in the exported JSON; nothing here knows a temperature.

import * as THREE from "three";
import type { Rgb } from "./aionStubs";

/** How far each star's colour is pushed from white for legibility. */
export const STAR_SATURATION_BOOST = 1.5;

/** A star's colour as drawn: its exported hue, saturation boosted, sRGB 0–1. */
export function starDisplayColour([r, g, b]: Rgb): Rgb {
  const top = Math.max(r, g, b);
  const push = (c: number) => Math.max(0, top - STAR_SATURATION_BOOST * (top - c));
  return [push(r), push(g), push(b)];
}

/** The same colour for three.js, read as sRGB (a plain THREE.Color(r, g, b) would take it as linear and wash it out). */
export function starDisplayThreeColour(rgb: Rgb): THREE.Color {
  const [r, g, b] = starDisplayColour(rgb);
  return new THREE.Color().setRGB(r, g, b, THREE.SRGBColorSpace);
}

/** A star's true colour for the light it casts: its exported hue unboosted, read as sRGB like the drawn colour. */
export function starLightThreeColour([r, g, b]: Rgb): THREE.Color {
  return new THREE.Color().setRGB(r, g, b, THREE.SRGBColorSpace);
}

/** The drawn colour as a CSS rgb() string. */
export function starDisplayCss(rgb: Rgb): string {
  const [r, g, b] = starDisplayColour(rgb);
  return `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`;
}
