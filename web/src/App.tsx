// The app: Star Builder (Phases 1-2), Experiments (Phase 3), Inside the Star (Phase 4), Planets (Phase 5)
// and System Timeline (Phase 6).
// Star Builder: pick a mass and [Fe/H] from the exported grid and scrub a star's life, then see its
// remnant. Every number shown comes from web/public/data, written by `python -m stellarforge.export
// web`; this file only selects, scales and draws.

import { memo, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { parseDocument, parseIndex, staleDataMessage } from "./data/loader";
import type { Grid, Meta, Provenance, Remnant, Track } from "./data/types";
import Experiments from "./Experiments";
import InsideTheStar from "./InsideTheStar";
import Planets from "./Planets";
import SystemTimeline, { type TimelineTarget } from "./SystemTimeline";
import ProvTag from "./ProvTag";
import StarNote from "./StarNote";
import { MetaContext } from "./data/metaContext";
import { SUN_TODAY, indexAtAge, nearest, skipWhileHidden, type CurrentStar, type StarProps, type View } from "./currentStar";
import { BLACK_HOLE_DISTANCE, BlackHoleView, START_ELEVATION_DEG } from "./rendering/blackHole/BlackHoleView";
import { starDisplayCss } from "./rendering/starColour";

const DATA = `${import.meta.env.BASE_URL}data/`;
const FIRST_FILE = "tracks_feh_+0.0.json";

interface GridFile {
  meta: Meta;
  grid: Grid;
}

const cache = new Map<string, Promise<GridFile>>();
function load(file: string): Promise<GridFile> {
  if (!cache.has(file)) {
    cache.set(file, fetch(DATA + file).then((r) => {
      if (!r.ok) throw new Error(`${file}: HTTP ${r.status}; run \`make export\``);
      return r.json();
    }).then((raw) => {
      const { meta, grid } = parseDocument(raw);
      if (!grid) throw new Error(`${file} holds no grid`);
      return { meta, grid };
    }));
  }
  return cache.get(file)!;
}

/** Slider steps go one [Fe/H] at a time, so the neighbours are fetched ahead (a first load takes ~60 ms).
 * Files more than two steps away are dropped, so a full sweep does not keep all 46 grids in memory. */
function prefetchAround({ grid }: GridFile) {
  const k = grid.feh_values.indexOf(grid.feh);
  for (const file of cache.keys()) {
    if (Math.abs(grid.files.indexOf(file) - k) > 2) cache.delete(file);
  }
  for (const file of [grid.files[k - 1], grid.files[k + 1]]) {
    if (file) load(file).catch(() => cache.delete(file));
  }
}

const fmt = (x: number, digits = 4) => x.toPrecision(digits);

export default function App() {
  const [view, setView] = useState<View>("star");
  // Other views load on first opening; after that every view stays mounted and keeps its state
  const [opened, setOpened] = useState(new Set<View>(["star"]));
  const show = (v: View) => {
    setView(v);
    setOpened((o) => new Set(o).add(v));
  };
  // The current star and time, shared by the star-aware views (currentStar.ts); opens on the Sun today
  const [star, setStar] = useState<CurrentStar>(SUN_TODAY);
  const shared = { star, setStar, show };
  const [target, setTarget] = useState<TimelineTarget | null>(null);
  const openTimeline = (t: TimelineTarget) => {
    setTarget(t);
    show("timeline");
  };
  // Stale data is named here, before a view opens the file and fails on it
  const [stale, setStale] = useState<string | null>(null);
  useEffect(() => {
    fetch(`${DATA}index.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((raw) => setStale(staleDataMessage(parseIndex(raw))))
      .catch((e: Error) => setStale(`No data index (${e.message}). Run make data-status, or make all-data if nothing is exported yet.`));
  }, []);
  return (
    <>
      {stale && <p className="stale-data" role="alert">{stale}</p>}
      <nav className="tabs" aria-label="Views">
        <button aria-pressed={view === "star"} onClick={() => show("star")}>Star Builder</button>
        <button aria-pressed={view === "experiments"} onClick={() => show("experiments")}>Experiments</button>
        <button aria-pressed={view === "inside"} onClick={() => show("inside")}>Inside the Star</button>
        <button aria-pressed={view === "planets"} onClick={() => show("planets")}>Planets</button>
        <button aria-pressed={view === "timeline"} onClick={() => show("timeline")}>System Timeline</button>
      </nav>
      <div hidden={view !== "star"}><StarBuilder {...shared} active={view === "star"} /></div>
      {opened.has("experiments") && <div hidden={view !== "experiments"}><Experiments /></div>}
      {opened.has("inside") && <div hidden={view !== "inside"}><InsideTheStar {...shared} active={view === "inside"} /></div>}
      {opened.has("planets") && <div hidden={view !== "planets"}><Planets {...shared} active={view === "planets"} onOpenTimeline={openTimeline} /></div>}
      {opened.has("timeline") && <div hidden={view !== "timeline"}><SystemTimeline {...shared} active={view === "timeline"} target={target} /></div>}
    </>
  );
}

const StarBuilder = memo(function StarBuilder({ star, setStar, show }: StarProps) {
  const [doc, setDoc] = useState<GridFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The age slider's own position, exact even where two exported points share an age. Null follows
  // the current age: after another star is picked, here or in another view, the age is kept.
  const [point, setPoint] = useState<number | null>(null);
  const [seen, setSeen] = useState(star);
  if (star !== seen) {
    setSeen(star);
    setPoint(null);
  }

  // The first file gives the grid's [Fe/H] values; after that, the file nearest the current [Fe/H].
  // A slower, older request is dropped when it lands.
  const file = doc ? doc.grid.files[nearest(doc.grid.feh_values, star.feh)] : FIRST_FILE;
  useEffect(() => {
    let live = true;
    load(file).then((d) => {
      if (!live) return;
      setDoc(d);
      prefetchAround(d);
    }, (e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [file]);

  if (error) return <main><p role="alert">{error}</p></main>;
  if (!doc) return <main><p>Loading tracks…</p></main>;

  const { grid } = doc;
  const massIndex = nearest(grid.mass_values_msun, star.mass_msun, true);
  const track = grid.tracks[massIndex];
  const i = Math.min(point ?? indexAtAge(track.age_yr, star.age_yr), track.age_yr.length - 1);
  const fehIndex = nearest(grid.feh_values, star.feh);
  const loaded = grid.files[fehIndex] === file && grid.feh === grid.feh_values[fehIndex];

  const pickMass = (k: number) => setStar({ ...star, mass_msun: grid.mass_values_msun[k] });
  const pickFeh = (k: number) => setStar({ ...star, feh: grid.feh_values[k] });
  const pickPoint = (k: number) => {
    // Marked as seen, so this view's own age does not come back as another view's choice
    const next = { ...star, age_yr: track.age_yr[k] };
    setSeen(next);
    setPoint(k);
    setStar(next);
  };

  return (
    <MetaContext value={doc.meta}>
    <main className="builder">
      <header>
        <h1>Star Builder</h1>
        <p className="source">{doc.meta.dataset}</p>
        <p className="note">
          This star in other views:{" "}
          <button className="linklike" onClick={() => show("inside")}>inside the star</button>{" · "}
          <button className="linklike" onClick={() => show("planets")}>its planets</button>{" · "}
          <button className="linklike" onClick={() => show("timeline")}>their fate as it ages</button>
        </p>
        {loaded && <StarNote star={star} shown={{ mass_msun: track.mass_msun, feh: grid.feh }} />}
      </header>

      <section className="controls" aria-label="Star">
        <label>
          Initial mass <output>{fmt(track.mass_msun)} M☉</output>
          <input type="range" min={0} max={grid.mass_values_msun.length - 1} value={massIndex}
            onChange={(e) => pickMass(Number(e.target.value))} />
        </label>
        <label>
          [Fe/H] <output>{grid.feh.toFixed(1)}</output>
          <input type="range" min={0} max={grid.feh_values.length - 1} value={fehIndex}
            onChange={(e) => pickFeh(Number(e.target.value))} />
        </label>
        <label>
          Age <output>{(track.age_yr[i] / 1e9).toPrecision(6)} Gyr</output>
          <input type="range" min={0} max={track.age_yr.length - 1} value={i}
            onChange={(e) => pickPoint(Number(e.target.value))} />
        </label>
      </section>

      <div className="views">
        <HrDiagram track={track} point={i} />
        <StarDisc track={track} point={i} />
      </div>

      <PhaseTimeline track={track} point={i} onPick={pickPoint} />
      <Numbers track={track} point={i} />
      <RemnantCard remnant={track.remnant} input={track.provenance} />
    </main>
    </MetaContext>
  );
}, skipWhileHidden);

function HrDiagram({ track, point }: { track: Track; point: number }) {
  const W = 460, H = 340, PAD = 44;
  const cooling = track.remnant.cooling;
  const { x, y, path, coolingPath, xTicks, yTicks } = useMemo(() => {
    const extent = (v: number[]) => {
      const lo = Math.min(...v), hi = Math.max(...v), pad = Math.max(0.05, (hi - lo) * 0.06);
      return [lo - pad, hi + pad];
    };
    // The white dwarf's cooling track widens the axes, so both fit
    const [t0, t1] = extent([...track.log_teff_k, ...(cooling?.log_teff_k ?? [])]);
    const [l0, l1] = extent([...track.log_l_lsun, ...(cooling?.log_l_lsun ?? [])]);
    // Hot stars on the left, as in every HR diagram
    const x = (t: number) => PAD + ((t1 - t) / (t1 - t0)) * (W - PAD - 10);
    const y = (l: number) => 10 + ((l1 - l) / (l1 - l0)) * (H - PAD - 10);
    const ticks = (a: number, b: number) => {
      const step = [0.1, 0.2, 0.5, 1, 2].find((s) => (b - a) / s <= 7) ?? 5;
      const out = [];
      for (let v = Math.ceil(a / step) * step; v <= b; v += step) out.push(+v.toFixed(2));
      return out;
    };
    const line = (ts: number[], ls: number[]) => ts.map((t, k) => `${k ? "L" : "M"}${x(t).toFixed(1)},${y(ls[k]).toFixed(1)}`).join("");
    const path = line(track.log_teff_k, track.log_l_lsun);
    const coolingPath = cooling ? line(cooling.log_teff_k, cooling.log_l_lsun) : null;
    return { x, y, path, coolingPath, xTicks: ticks(t0, t1), yTicks: ticks(l0, l1) };
  }, [track, cooling]);

  return (
    <svg className="hr" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Hertzsprung–Russell diagram of the track">
      <rect x={PAD} y={10} width={W - PAD - 10} height={H - PAD - 10} className="frame" />
      {xTicks.map((t) => (
        <text key={`x${t}`} x={x(t)} y={H - PAD + 16} textAnchor="middle">{t}</text>
      ))}
      {yTicks.map((l) => (
        <text key={`y${l}`} x={PAD - 6} y={y(l) + 4} textAnchor="end">{l}</text>
      ))}
      <text x={(W + PAD) / 2} y={H - 6} textAnchor="middle">log T_eff (K)</text>
      <text transform={`translate(12 ${(H - PAD) / 2}) rotate(-90)`} textAnchor="middle">log L (L☉)</text>
      <path d={path} className="track" />
      {coolingPath && <path d={coolingPath} className="cooling"><title>White-dwarf cooling (Bédard et al. 2020)</title></path>}
      <circle cx={x(track.log_teff_k[point])} cy={y(track.log_l_lsun[point])} r={6}
        fill={starDisplayCss(track.rgb[point])} stroke="#fff" />
    </svg>
  );
}

function StarDisc({ track, point }: { track: Track; point: number }) {
  // Display scale only: log radius maps to pixels, clamped to the panel
  const size = Math.min(220, Math.max(6, 60 * 2 ** (track.log_r_rsun[point] * 1.2)));
  const colour = starDisplayCss(track.rgb[point]);
  return (
    <div className="disc-panel">
      <div className="star" role="img" aria-label="The star, coloured and sized by its exported values"
        style={{ width: size, height: size, background: colour, boxShadow: `0 0 ${size / 3}px ${size / 8}px ${colour}` }} />
      <p className="note">Size on a log scale; colour boosted for legibility</p>
    </div>
  );
}

const PHASE_COLOURS: Record<string, string> = {
  "-1": "#6b5b95", "0": "#3f7fbf", "2": "#d9822b", "3": "#c4a000", "4": "#b5523b",
  "5": "#8c2f39", "6": "#9aa0a6", "9": "#2a9d8f",
};

function PhaseTimeline({ track, point, onPick }: { track: Track; point: number; onPick: (k: number) => void }) {
  const names = track.phase_names;
  const runs: { phase: number; start: number; end: number }[] = [];
  track.phase.forEach((p, k) => {
    const last = runs[runs.length - 1];
    if (last && last.phase === p) last.end = k;
    else runs.push({ phase: p, start: k, end: k });
  });
  const n = track.phase.length;
  return (
    <section aria-label="Phases" className="timeline">
      <div className="bar">
        {runs.map((r) => (
          <button key={r.start} title={names[r.phase]} onClick={() => onPick(r.start)}
            style={{ flexGrow: r.end - r.start + 1, background: PHASE_COLOURS[r.phase] ?? "#555" }}>
            {(r.end - r.start + 1) / n > 0.12 ? names[r.phase] : ""}
          </button>
        ))}
        <span className="cursor" style={{ left: `${(100 * (point + 0.5)) / n}%` }} />
      </div>
      <p className="note">Widths follow evolutionary stages (MIST EEPs), not time.</p>
    </section>
  );
}

function Numbers({ track, point }: { track: Track; point: number }) {
  const fp = track.field_provenance;
  const names = track.phase_names;
  const rows: [string, string, Provenance][] = [
    ["Age", `${(track.age_yr[point] / 1e9).toPrecision(6)} Gyr`, fp.age_yr],
    ["Phase", names[track.phase[point]] ?? String(track.phase[point]), fp.phase],
    ["Mass now", `${fmt(track.mass_now_msun[point])} M☉`, fp.mass_now_msun],
    ["log L", `${track.log_l_lsun[point]} L☉`, fp.log_l_lsun],
    ["log T_eff", `${track.log_teff_k[point]} K`, fp.log_teff_k],
    ["log R", `${track.log_r_rsun[point]} R☉`, fp.log_r_rsun],
    ["Colour (sRGB)", track.rgb[point].join(", "), fp.rgb],
  ];
  return (
    <section aria-label="Values" className="numbers">
      <dl>
        {rows.map(([name, value, p]) => (
          <div key={name}><dt>{name}</dt><dd>{value} <ProvTag p={p} what={`${name}: ${value}`} how={track.method} flags={track.flags} /></dd></div>
        ))}
        <div><dt>Track</dt><dd>{track.method}</dd></div>
        <div><dt>Track ends at</dt><dd>{track.ending}</dd></div>
        {track.flags.length > 0 && <div><dt>Warnings</dt><dd className="flags">{track.flags.join("; ")}</dd></div>}
      </dl>
    </section>
  );
}

const REMNANT_TITLES: Record<Remnant["type"], string> = {
  "white dwarf": "White dwarf", "neutron star": "Neutron star", "black hole": "Black hole",
  none: "No remnant", "not yet": "No remnant yet", "not predicted": "Not predicted",
};

/** The remnant under the adopted prescription or, with the toggle, the other one the file carries. */
function RemnantCard({ remnant, input }: { remnant: Remnant; input: Provenance }) {
  // Kept from star to star, so a sweep in mass can be watched under either prescription
  const [other, setOther] = useState(false);
  const hasOther = remnant.alternative.prescription !== "no alternative";
  const r = other && hasOther ? { ...remnant, ...remnant.alternative } : remnant;
  const notShown = other && hasOther ? remnant : remnant.alternative;
  const mass = (m: number | null) => (m === null ? "—" : `${m} M☉`);
  return (
    <section aria-label="Remnant" className="remnant">
      {hasOther && (
        <div className="subtabs prescriptions" role="group" aria-label="Remnant prescription">
          Prescription:
          <button aria-pressed={!other} onClick={() => setOther(false)}>{remnant.prescription} (adopted)</button>
          <button aria-pressed={other} onClick={() => setOther(true)}>{remnant.alternative.prescription}</button>
        </div>
      )}
      <h2>{REMNANT_TITLES[r.type]}{r.mass_msun !== null && <> · {r.mass_msun} M☉ <ProvTag p={r.provenance} what={`Remnant mass: ${r.mass_msun} M☉`} how={r.prescription} flags={r.flags} /></>}</h2>
      <p>{r.how}</p>
      <dl>
        {r.radius_km !== null && (
          <div><dt>{r.type === "black hole" ? "Horizon radius" : r.type === "white dwarf" ? "Radius (cooled)" : "Radius"}</dt><dd>{r.radius_km} km</dd></div>
        )}
        <div><dt>Prescription</dt><dd>{r.prescription}</dd></div>
        <div><dt>From a track that is</dt><dd><ProvTag p={input} what="The star's track" flags={r.flags} /></dd></div>
        <div><dt>{other && hasOther ? "Adopted prescription" : "Alternative"}</dt><dd>{notShown.prescription}: {notShown.type}, {mass(notShown.mass_msun)}</dd></div>
        <div><dt>Final mass · helium core · CO core</dt><dd>{mass(r.final_mass_msun)} · {mass(r.he_core_mass_msun)} · {mass(r.co_core_mass_msun)}</dd></div>
        {r.cooling && <div><dt>Cooling (Bédard et al. 2020){other && hasOther && ", for the MIST final mass"}</dt><dd>dashed on the HR diagram, to {(r.cooling.cooling_age_yr[r.cooling.cooling_age_yr.length - 1] / 1e9).toPrecision(3)} Gyr</dd></div>}
        <div><dt>Warnings</dt><dd className="flags">{r.flags.join("; ")}</dd></div>
      </dl>
      <BlackHoleCanvas show={r.type === "black hole"} />
    </section>
  );
}

/**
 * The copied lensing view at its lowest quality, redrawn only when the camera moves. It works in
 * horizon radii, so every black hole looks the same from the same distance; it is built once, on the
 * first black hole shown (a WebGL context and a shader compile cost ~0.5 s), then only hidden.
 */
function BlackHoleCanvas({ show }: { show: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [built, setBuilt] = useState(show);
  if (show && !built) setBuilt(true);
  useEffect(() => {
    if (!built) return;
    let cleanup = () => {};
    // After this frame paints, so the slider that showed the black hole is not held up
    const timer = setTimeout(() => {
      const canvas = document.createElement("canvas");
      canvas.setAttribute("aria-label", "Gravitational lensing of the background sky by the black hole");
      ref.current!.append(canvas);
      const renderer = new THREE.WebGLRenderer({ canvas });
      renderer.setPixelRatio(1);
      renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
      const camera = new THREE.PerspectiveCamera(40, canvas.clientWidth / canvas.clientHeight, 0.1, 1000);
      const elevation = THREE.MathUtils.degToRad(START_ELEVATION_DEG);
      camera.position.set(0, Math.sin(elevation), Math.cos(elevation)).multiplyScalar(BLACK_HOLE_DISTANCE.start);
      const controls = new OrbitControls(camera, canvas);
      controls.minDistance = BLACK_HOLE_DISTANCE.min;
      controls.maxDistance = BLACK_HOLE_DISTANCE.max;
      // No gas around an isolated stellar black hole; the horizon radius only sets the view's km scale,
      // which this page does not draw. The seed only places the background stars.
      const view = new BlackHoleView({ horizonRadiusKm: 1, accretionMode: "none", discPeakTemperatureK: 0 }, 0.37, "spiral", false, performance.now(), "standard");
      const draw = () => view.render(renderer, camera, performance.now());
      controls.addEventListener("change", draw);
      draw();
      cleanup = () => {
        controls.dispose();
        view.dispose();
        renderer.dispose();
        renderer.forceContextLoss();
        canvas.remove();
      };
    }, 0);
    return () => {
      clearTimeout(timer);
      cleanup();
    };
  }, [built]);
  return (
    <figure className="bh" hidden={!show}>
      <div ref={ref} />
      <figcaption className="note">
        Light bent by the black hole, seen from {BLACK_HOLE_DISTANCE.start} horizon radii (drag to orbit). Every black hole looks
        the same at the same distance in horizon radii; its background sky is illustrative.
      </figcaption>
    </figure>
  );
}
