// The 3D system view (Phase 7 step 4): System Timeline's map drawn with the copied Aion Forge system
// view (rendering/system/). Optional, behind the view's 3D toggle; the 2D map stays the default.
// Every orbit (a, e), the star's radius and colour and the habitable zone come from the timeline
// file at the scrubber's age, exactly as the 2D map reads them. Where a planet is along its ellipse
// is animation only: the Kepler solve and the pacing (the innermost goes round in a minute) are
// drawing, as in Aion Forge. Orbits are to scale; planets, and a star smaller than this, are enlarged.

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Rgb } from "./data/types";
import { starDisplayThreeColour, starLightThreeColour } from "./rendering/starColour";
import {
  disposeSystemGroup, hostStarObject, keplerLine, keplerPlace, secondsPerOrbit, systemLights, SYSTEM_UNITS_PER_AU,
  type KeplerPath,
} from "./rendering/system/systemView";

/** One age of one system, as the 2D map draws it; a null planet is not there (not yet formed, or gone). */
export interface SystemFrame {
  starRadiusAu: number;
  rgb: Rgb;
  hzInAu: number | null;
  hzOutAu: number | null;
  planets: ({ a_au: number; e: number; colour: string; size: number } | null)[];
}

const HZ_COLOUR = 0x3f8f5a;
// Display sizes as shares of the system's extent (the largest apocentre), and of each planet's own
// pericentre, so an inner planet never covers its star
const PLANET_SHARE_OF_EXTENT = 0.008;
const PLANET_SHARE_OF_PERICENTRE = 0.2;
const STAR_SHARE_OF_EXTENT = 0.004;
const STAR_SHARE_OF_INNERMOST = 0.3;
const MAX_SIZE = { width: 1280, height: 720 };

export default function SystemView3D({ frame, extentAu, label }: { frame: SystemFrame; extentAu: number; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const frameRef = useRef(frame);
  useEffect(() => {
    frameRef.current = frame;
  }, [frame]);
  useEffect(() => {
    const canvas = document.createElement("canvas");
    ref.current!.append(canvas);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(1);
    const scene = new THREE.Scene();
    const E = extentAu * SYSTEM_UNITS_PER_AU;
    const camera = new THREE.PerspectiveCamera(40, 16 / 10, E * 1e-4, E * 100);
    const elevation = THREE.MathUtils.degToRad(35);
    camera.position.set(0, Math.sin(elevation), Math.cos(elevation)).multiplyScalar(1.5 * E);
    const controls = new OrbitControls(camera, canvas);
    controls.minDistance = E * 0.003;
    controls.maxDistance = E * 6;
    let dirty = true;
    controls.addEventListener("change", () => { dirty = true; });

    const world = new THREE.Group();
    scene.add(world);
    let star: THREE.Group | null = null;
    let starRgb = "";
    let hz: THREE.Mesh | null = null;
    let lights: THREE.Light[] = [];
    // Per planet: its orbit line, its sphere, the a and e it was drawn for, and its mean anomaly
    const bodies = new Map<number, { line: THREE.LineLoop; ball: THREE.Mesh; a: number; e: number; M: number }>();
    let drawn: SystemFrame | null = null;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const replace = (old: THREE.Object3D | null, next: THREE.Object3D | null) => {
      if (old) { world.remove(old); disposeSystemGroup(old); }
      if (next) world.add(next);
    };

    /** Rebuilds what changed since the last frame drawn. */
    const sync = (f: SystemFrame) => {
      const present = f.planets.flatMap((p) => (p ? [p.a_au * (1 - p.e)] : []));
      const innermost = present.length ? Math.min(...present) * SYSTEM_UNITS_PER_AU : Infinity;
      const starRadius = Math.max(f.starRadiusAu * SYSTEM_UNITS_PER_AU, Math.min(E * STAR_SHARE_OF_EXTENT, STAR_SHARE_OF_INNERMOST * innermost));
      const key = f.rgb.join();
      if (key !== starRgb) {
        starRgb = key;
        const next = hostStarObject(starDisplayThreeColour(f.rgb), 1);
        replace(star, next);
        star = next;
        for (const l of lights) world.remove(l);
        lights = systemLights(starLightThreeColour(f.rgb));
        world.add(...lights);
      }
      star!.scale.setScalar(starRadius);
      if (!drawn || f.hzInAu !== drawn.hzInAu || f.hzOutAu !== drawn.hzOutAu) {
        const next = f.hzInAu !== null && f.hzOutAu !== null
          ? new THREE.Mesh(
            new THREE.RingGeometry(f.hzInAu * SYSTEM_UNITS_PER_AU, f.hzOutAu * SYSTEM_UNITS_PER_AU, 128).rotateX(-Math.PI / 2),
            new THREE.MeshBasicMaterial({ color: HZ_COLOUR, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false }))
          : null;
        replace(hz, next);
        hz = next;
      }
      f.planets.forEach((p, k) => {
        const body = bodies.get(k);
        if (!p) {
          if (body) { replace(body.line, null); replace(body.ball, null); bodies.delete(k); }
          return;
        }
        const size = Math.min(E * PLANET_SHARE_OF_EXTENT * p.size, PLANET_SHARE_OF_PERICENTRE * p.a_au * (1 - p.e) * SYSTEM_UNITS_PER_AU);
        if (body && body.a === p.a_au && body.e === p.e) {
          body.ball.scale.setScalar(size);
          return;
        }
        const line = keplerLine(pathOf(k, p.a_au, p.e), 0x4a525d, 0.7);
        replace(body?.line ?? null, line);
        let ball = body?.ball;
        if (!ball) {
          ball = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16), new THREE.MeshStandardMaterial({ color: p.colour, roughness: 0.9 }));
          world.add(ball);
        }
        ball.scale.setScalar(size);
        bodies.set(k, { line, ball, a: p.a_au, e: p.e, M: body?.M ?? 0 });
      });
      drawn = f;
    };

    /** Moves each planet on by dt seconds along its ellipse; the innermost takes a minute per turn. */
    const advance = (dt: number) => {
      const inner = Math.min(...[...bodies.values()].map((b) => b.a));
      bodies.forEach((b, k) => {
        b.M = (b.M + (2 * Math.PI * dt) / secondsPerOrbit(b.a, inner)) % (2 * Math.PI);
        const [x, z] = keplerPlace(pathOf(k, b.a, b.e), b.M);
        b.ball.position.set(x, 0, z);
      });
    };

    let raf = 0, last = performance.now();
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (canvas.offsetParent === null) return;   // the view's tab is hidden
      const w = Math.min(MAX_SIZE.width, canvas.clientWidth), h = Math.min(MAX_SIZE.height, canvas.clientHeight);
      if (canvas.width !== w || canvas.height !== h) {
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        dirty = true;
      }
      if (frameRef.current !== drawn) { sync(frameRef.current); dirty = true; }
      if (!reducedMotion || dirty) {
        advance(reducedMotion ? 0 : dt);
        renderer.render(scene, camera);
        dirty = false;
      }
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      controls.dispose();
      disposeSystemGroup(world);
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
    };
  }, [extentAu]);
  return <div ref={ref} className="system-3d" role="img" aria-label={label} />;
}

/** Each planet's ellipse turned to the same pericentre direction as in the 2D map. */
function pathOf(k: number, a_au: number, e: number): KeplerPath {
  return { a: a_au * SYSTEM_UNITS_PER_AU, e, share: 1, periapsis: (k * 2.4) % (2 * Math.PI) };
}
